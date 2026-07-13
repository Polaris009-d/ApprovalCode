"""
BaseTool — 工具基类
参考 Claude Code 工具系统：每个工具是一个独立模块，
有明确的 Schema、执行函数、重试逻辑
"""
import time
import traceback
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

from ..models.schemas import ToolCall, ToolResult


class BaseTool(ABC):
    """
    工具基类，所有审批工具继承此类。

    参考 Claude Code Tool 协议：
    - name: 工具名（唯一标识）
    - description: 给 Agent 看的功能描述
    - input_schema: Pydantic 模型，用于参数校验
    - max_retries: 失败重试上限
    """

    name: str
    description: str
    input_schema: Type[BaseModel]
    max_retries: int = 3
    require_approval: bool = False

    async def execute(self, call: ToolCall, **kwargs) -> ToolResult:
        """
        执行工具调用，带自动重试。
        等同 Claude Code 的 tool invocation + retry 逻辑。
        """
        start = time.perf_counter()
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                # 1. Schema 校验 — 参考 Claude Code 的 JSON Schema validation
                validated = self.input_schema(**call.arguments)

                # 2. 执行 — 子类实现
                result_data = await self._run(validated, call=call, **kwargs)

                # 3. 构造返回
                elapsed = (time.perf_counter() - start) * 1000
                return ToolResult(
                    call_id=call.call_id,
                    success=True,
                    data=result_data,
                    retry_count=attempt,
                    latency_ms=round(elapsed, 2),
                )

            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    # 指数退避重试 — 1s, 2s, 4s ...
                    await self._backoff(attempt)
                    continue

        # 全部重试失败
        elapsed = (time.perf_counter() - start) * 1000
        return ToolResult(
            call_id=call.call_id,
            success=False,
            error=f"{last_error}\n{traceback.format_exc()}",
            retry_count=self.max_retries,
            latency_ms=round(elapsed, 2),
        )

    @abstractmethod
    async def _run(self, validated_input: BaseModel, call: ToolCall, **kwargs) -> Any:
        """
        子类实现：执行具体逻辑。
        输入已经过 Pydantic 校验。
        返回任意可 JSON 序列化的数据。
        """
        ...

    async def _backoff(self, attempt: int):
        """指数退避"""
        import asyncio
        delay = 2 ** attempt  # 1s, 2s, 4s
        await asyncio.sleep(delay)

    def to_schema(self) -> Dict[str, Any]:
        """导出工具的 JSON Schema — Agent 通过此信息决策调用哪个工具"""
        return {
            "name": self.name,
            "description": self.description,
            "require_approval": self.require_approval,
            "parameters": self.input_schema.model_json_schema(),
        }
