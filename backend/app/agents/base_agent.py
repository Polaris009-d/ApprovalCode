"""
BaseAgent — Agent 基类
参考 Claude Code Agent 架构：统一的 setup → think → act → observe → teardown 生命周期
"""
import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from ..models.schemas import (
    AgentState, AgentStatus, ReActStep, ReActStepType,
    ToolCall, ToolResult, ApprovalTask
)
from ..tools.registry import ToolRegistry


class BaseAgent(ABC):
    """
    Agent 基类。

    参考 Claude Code Subagent 设计：
    - 每个 Agent 有绑定的 ToolRegistry
    - 统一的 ReAct (Reasoning + Acting) 循环
    - 步骤级审计日志
    - 超时控制
    """

    agent_type: str = "base"                 # master / extract / comply / risk
    max_steps: int = 10                      # ReAct 最大步数
    timeout: int = 60                        # 超时秒数

    def __init__(self):
        self.agent_id: str = f"{self.agent_type}_{uuid.uuid4().hex[:8]}"
        self.state = AgentState(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
        )
        self.tools: ToolRegistry = ToolRegistry()
        self.trace: List[ReActStep] = []     # 步骤追踪
        self._cancelled = False

    # ──── 生命周期 ────

    async def execute(self, task: ApprovalTask, context: Dict[str, Any]) -> Tuple[Any, List[ReActStep]]:
        """
        入口：执行 Agent。
        返回 (结果, 完整步骤追踪)
        """
        self.state.status = AgentStatus.THINKING
        self.state.started_at = datetime.utcnow()
        step_num = 0

        try:
            # 1. Setup — 注册工具、初始化
            await self.setup(task, context)

            # 2. ReAct 循环 — 参考 Claude Code nO 主循环
            while step_num < self.max_steps and not self._cancelled:
                step_num += 1
                self.state.current_step = step_num

                # — THINK —
                step_start = time.perf_counter()
                thought = await self.think(context)
                latency = (time.perf_counter() - step_start) * 1000
                self._record_step(step_num, ReActStepType.THINK, content=thought, latency_ms=latency)
                self.state.thought = thought
                self.state.status = AgentStatus.THINKING

                # — PLAN — (Master Agent 用；子 Agent 可能跳过)
                step_start = time.perf_counter()
                plan = await self.plan(thought, context)
                latency = (time.perf_counter() - step_start) * 1000
                self._record_step(step_num, ReActStepType.PLAN, content=str(plan), latency_ms=latency)
                self.state.plan = plan
                self.state.status = AgentStatus.THINKING

                # — ACT + OBSERVE —
                self.state.status = AgentStatus.ACTING
                done, result = await self.act_and_observe(step_num, plan, context)

                if done:
                    self.state.status = AgentStatus.DONE
                    return await self.teardown(result, context), self.trace

            # 超出最大步数
            resultado = {"warning": f"Reached max steps ({self.max_steps})"}
            self.state.status = AgentStatus.DONE
            return await self.teardown(resultado, context), self.trace

        except asyncio.TimeoutError:
            self.state.status = AgentStatus.ERROR
            self.state.context["error"] = f"Agent timed out after {self.timeout}s"
            return {"error": "timeout"}, self.trace
        except Exception as e:
            import traceback
            print(f"[BaseAgent ERROR] {e}")
            traceback.print_exc()
            self.state.status = AgentStatus.ERROR
            self.state.context["error"] = str(e)
            return {"error": str(e)}, self.trace

    async def act_and_observe(self, step_num: int, plan: Any, context: Dict) -> Tuple[bool, Any]:
        """
        ACT → OBSERVE 阶段，带重试。
        由 think/plan 决定调用哪个工具。
        """
        tool_name, tool_args = self._parse_plan(plan)

        if tool_name is None:
            # 无需调用工具 → 完成
            return True, context

        # 构造 ToolCall
        call = ToolCall(
            tool_name=tool_name,
            arguments=tool_args or {},
            agent_id=self.agent_id,
            step=step_num,
        )

        # ACT — 调用工具
        step_start = time.perf_counter()
        tool_result: ToolResult = await self.tools.call(call, context=context)
        latency = (time.perf_counter() - step_start) * 1000

        self._record_step(
            step_num, ReActStepType.ACT,
            content=f"call {tool_name}({tool_args})",
            tool_call=call,
            tool_result=tool_result,
            latency_ms=latency,
        )

        # OBSERVE — 解读结果
        observation = await self.observe(tool_result, context)
        self._record_step(
            step_num, ReActStepType.OBSERVE,
            content=observation,
            latency_ms=0,
        )

        # 更新 context
        if tool_result.success and tool_result.data:
            context[tool_name] = tool_result.data

        # 判断是否继续
        done = self._is_done(tool_result, context)
        return done, context

    # ──── 钩子方法 — 子类实现 ────

    @abstractmethod
    async def setup(self, task: ApprovalTask, context: Dict[str, Any]):
        """初始化：注册工具，加载知识等"""
        ...

    @abstractmethod
    async def think(self, context: Dict[str, Any]) -> str:
        """推理：分析当前状态，决定下一步"""
        ...

    @abstractmethod
    async def plan(self, thought: str, context: Dict[str, Any]) -> Any:
        """规划：将思想转化为具体行动 (tool_name, tool_args)"""
        ...

    @abstractmethod
    async def observe(self, result: ToolResult, context: Dict[str, Any]) -> str:
        """观察：解读工具返回结果"""
        ...

    @abstractmethod
    async def teardown(self, result: Any, context: Dict[str, Any]) -> Any:
        """清理：汇总结果，释放资源"""
        ...

    # ──── 辅助 ────

    def _parse_plan(self, plan: Any) -> Tuple[Optional[str], Optional[Dict]]:
        """从 plan 中提取 (tool_name, tool_args)"""
        if isinstance(plan, tuple) and len(plan) == 2:
            return plan[0], plan[1]
        if isinstance(plan, dict):
            return plan.get("tool"), plan.get("args")
        return None, None

    def _is_done(self, result: ToolResult, context: Dict) -> bool:
        """默认：成功即完成。子类可覆盖以支持多步骤。"""
        return result.success

    def _record_step(self, step_num: int, step_type: ReActStepType,
                     content: str = "", tool_call: Optional[ToolCall] = None,
                     tool_result: Optional[ToolResult] = None, latency_ms: float = 0.0):
        """记录 ReAct 步骤"""
        step = ReActStep(
            step_num=step_num,
            agent_id=self.agent_id,
            step_type=step_type,
            content=content,
            tool_call=tool_call,
            tool_result=tool_result,
            latency_ms=round(latency_ms, 2),
        )
        self.trace.append(step)
        self.state.updated_at = datetime.utcnow()

    def cancel(self):
        """取消 Agent 执行"""
        self._cancelled = True
