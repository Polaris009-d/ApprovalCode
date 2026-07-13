"""
审计日志 + 全链路可观测
参考 Claude Code 的 agent transcript (JSONL) + 步骤追踪
"""
import json
import time
from typing import Any, Dict, List
from datetime import datetime
from ..models.schemas import ReActStep, ApprovalReport


class AuditLogger:
    """
    审计日志系统。

    参考 Claude Code observability:
    - 每一步 ReAct 实时落库
    - 前端时间轴通过此数据回放
    - 所有 Agent 操作不可篡改
    """

    def __init__(self):
        self._events: List[Dict[str, Any]] = []   # 内存缓冲
        self._reports: List[ApprovalReport] = []

    async def log_event(self, event_type: str, data: Dict[str, Any]):
        """记录事件"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._events.append(event)
        # TODO: 异步写入数据库

    async def log_step(self, step: ReActStep):
        """记录单个 ReAct 步骤 — 时间轴的最基本单元"""
        # 输出到 stdout（开发阶段）
        print(
            f"[AUDIT] step={step.step_num} agent={step.agent_id} "
            f"type={step.step_type.value} latency={step.latency_ms}ms "
            f"content={step.content[:80]}"
        )
        self._events.append({
            "type": "react_step",
            "data": step.model_dump(),
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def log_report(self, report: ApprovalReport):
        """保存完整审批报告"""
        self._reports.append(report)
        print(
            f"[AUDIT] report task={report.task_id} "
            f"status={report.status} risk={report.risk_level} "
            f"traces={len(report.agent_traces)} steps"
        )

    def get_timeline(self, task_id: str) -> List[Dict[str, Any]]:
        """
        获取时间轴数据 — 供前端回放。
        参考 Claude Code 的 agent transcript 回放。
        """
        steps = []
        for event in self._events:
            if event["type"] == "react_step":
                data = event["data"]
                steps.append({
                    "step": data["step_num"],
                    "agent": data["agent_id"],
                    "type": data["step_type"],
                    "content": data.get("content", ""),
                    "tool": data.get("tool_call", {}).get("tool_name") if data.get("tool_call") else None,
                    "duration_ms": data.get("latency_ms", 0),
                    "timestamp": event["timestamp"],
                })
        return steps

    def get_agent_statuses(self) -> Dict[str, str]:
        """获取所有 Agent 状态 — 供前端监控面板"""
        agent_states = {}
        for event in reversed(self._events):
            if event["type"] == "react_step":
                data = event["data"]
                agent_id = data.get("agent_id", "unknown")
                if agent_id not in agent_states:
                    agent_states[agent_id] = data.get("step_type", "unknown")
        return agent_states
