"""
ToolRegistry — 工具注册中心
参考 Claude Code Tool Registry：统一注册、查询、调用工具
"""
from typing import Dict, List, Optional
from .base_tool import BaseTool
from ..models.schemas import ToolCall, ToolResult


class ToolRegistry:
    """
    工具注册中心。

    参考 Claude Code 的工具管理：
    - 所有工具注册到 registry
    - Agent 通过 get_schemas() 获取可用工具列表
    - 通过 call() 统一调用
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._stats: Dict[str, dict] = {}

    def register(self, tool: BaseTool):
        """注册一个工具"""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def register_many(self, tools: List[BaseTool]):
        """批量注册"""
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str):
        """注销工具"""
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        """按名获取工具"""
        return self._tools.get(name)

    def get_schemas(self) -> List[dict]:
        """
        获取所有工具的 Schema 列表
        Agent 通过此方法了解可用的工具和参数
        """
        return [tool.to_schema() for tool in self._tools.values()]

    def get_available_tools(self) -> List[str]:
        """获取所有可用工具名"""
        return list(self._tools.keys())

    async def call(self, call: ToolCall, **kwargs) -> ToolResult:
        tool = self._tools.get(call.tool_name)
        if tool is None:
            return ToolResult(call_id=call.call_id, success=False,
                error=f"Unknown tool: '{call.tool_name}'. Available: {self.get_available_tools()}")
        result = await tool.execute(call, **kwargs)
        # 统计
        if call.tool_name not in self._stats:
            self._stats[call.tool_name] = {"calls": 0, "success": 0, "total_latency": 0.0}
        self._stats[call.tool_name]["calls"] += 1
        if result.success: self._stats[call.tool_name]["success"] += 1
        self._stats[call.tool_name]["total_latency"] += result.latency_ms
        return result


# 全局单例
registry = ToolRegistry()
