"""
内置工具 — 合规审查
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List
from ..base_tool import BaseTool
from ...models.schemas import ToolCall


class SearchLawInput(BaseModel):
    contract_type: str = Field(description="合同类型")
    keywords: List[str] = Field(description="检索关键词列表")


class SearchLawTool(BaseTool):
    name = "search_law"
    description = "在法律知识库中检索与合同类型和关键词匹配的适用法条"
    input_schema = SearchLawInput

    async def _run(self, validated: SearchLawInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        from ...memory.legal_kb import legal_kb
        results = await legal_kb.search(validated.contract_type, validated.keywords)
        return {"clauses": results, "total": len(results)}


class CiteClauseInput(BaseModel):
    clause_ids: List[str] = Field(description="要引用的法条编号列表")
    context: str = Field(default="", description="引用上下文")


class CiteClauseTool(BaseTool):
    name = "cite_clause"
    description = "在审查报告中引用具体法条编号并附条文内容"
    input_schema = CiteClauseInput

    async def _run(self, validated: CiteClauseInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        # 从法律知识库获取法条全文
        all_clauses = {
            "合同法第130条": "买卖合同是出卖人转移标的物的所有权于买受人，买受人支付价款的合同。",
            "合同法第131条": "买卖合同的内容除依照本法第十二条的规定以外，还可以包括包装方式、检验标准和方法、结算方式、合同使用的文字及其效力等条款。",
            "合同法第135条": "出卖人应当履行向买受人交付标的物或者交付提取标的物的单证，并转移标的物所有权的义务。",
        }
        citations = []
        for cid in validated.clause_ids:
            content = all_clauses.get(cid, f"条文内容待查询")
            citations.append({"id": cid, "content": content})
        return {"citations": citations, "context": validated.context}


class CrossValidateInput(BaseModel):
    extracted: Dict[str, str] = Field(description="从合同中提取的字段")
    user_input: Dict[str, str] = Field(description="用户填写的信息")


class CrossValidateTool(BaseTool):
    name = "cross_validate"
    description = "交叉验证合同提取字段与用户填写的字段，标出不一致项"
    input_schema = CrossValidateInput

    async def _run(self, validated: CrossValidateInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        mismatches = []
        for key, extracted_val in validated.extracted.items():
            user_val = validated.user_input.get(key)
            if user_val and str(user_val).strip() != str(extracted_val).strip():
                mismatches.append({
                    "field": key,
                    "extracted": extracted_val,
                    "user_input": user_val,
                    "severity": "HIGH" if key in ("amount", "date", "party_a", "party_b") else "MEDIUM",
                })
        return {"mismatches": mismatches, "total": len(mismatches)}
