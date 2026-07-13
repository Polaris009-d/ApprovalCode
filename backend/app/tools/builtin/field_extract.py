"""
内置工具 — 字段提取与验证
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from ..base_tool import BaseTool
from ...models.schemas import ToolCall


class ExtractFieldsInput(BaseModel):
    files: List[str] = Field(description="合同文件路径列表")
    contract_type: str = Field(description="合同类型")


class ExtractFieldsTool(BaseTool):
    name = "extract_fields"
    description = "从合同文件中提取关键字段（甲方、乙方、金额、日期等）"
    input_schema = ExtractFieldsInput

    async def _run(self, validated: ExtractFieldsInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        # TODO: 集成 OCR + 视觉模型
        # 当前返回模拟数据
        return {
            "fields": {
                "party_a": "XX科技有限公司",
                "party_b": "YY贸易有限公司",
                "amount": "1,000,000",
                "date": "2025-06-01",
                "subject": "ERP系统开发服务",
            },
            "source_files": validated.files,
        }


async def extract_fields_and_validate(files: List[str], contract_type: str):
    """便捷函数：直接提取字段"""
    tool = ExtractFieldsTool()
    call = ToolCall(
        tool_name="extract_fields",
        arguments={"files": files, "contract_type": contract_type},
        agent_id="direct",
    )
    return await tool.execute(call)
