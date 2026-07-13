"""
内置工具 — 风险评估与审批决策
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from ..base_tool import BaseTool
from ...models.schemas import ToolCall, PermissionDecision


class RiskScoreInput(BaseModel):
    mismatch_count: int = Field(default=0, description="字段不一致数量")
    citation_count: int = Field(default=0, description="引用法条数量")
    contract_amount: float = Field(default=0, description="合同金额（元）")
    has_sensitive_clauses: bool = Field(default=False, description="是否包含敏感条款")


class RiskScoreTool(BaseTool):
    name = "risk_score"
    description = "多维度风险评估，返回综合风险评分和等级"
    input_schema = RiskScoreInput

    async def _run(self, validated: RiskScoreInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        breakdown = []

        # 金额因子
        amount_score = 0
        amount_rule = ""
        if validated.contract_amount > 1_000_000:
            amount_score = 40
            amount_rule = f"金额 {validated.contract_amount/10000:.0f}万 > 100万"
        elif validated.contract_amount > 500_000:
            amount_score = 25
            amount_rule = f"金额 {validated.contract_amount/10000:.0f}万 > 50万"
        elif validated.contract_amount > 100_000:
            amount_score = 10
            amount_rule = f"金额 {validated.contract_amount/10000:.0f}万 > 10万"
        else:
            amount_rule = f"金额 {validated.contract_amount}元 <= 10万"
        breakdown.append({"name": "金额因子", "score": amount_score, "max": 40, "detail": amount_rule})

        # 风险模式命中因子 (mismatch_count 复用为风险模式命中数)
        pattern_score = min(validated.mismatch_count * 10, 60)
        if validated.mismatch_count > 0:
            pattern_rule = f"{validated.mismatch_count} 个风险模式命中 × 10分 = {pattern_score}分"
        else:
            pattern_rule = "无风险模式命中"
        breakdown.append({"name": "风险模式命中", "score": pattern_score, "max": 60, "detail": pattern_rule})

        # 法条引用 — 仅供审查报告展示法律依据，不影响风险评分
        cite_rule = f"匹配 {validated.citation_count} 条法条（法律依据，不计分）" if validated.citation_count > 0 else "未匹配法条"

        # 敏感条款
        sensitive_score = 20 if validated.has_sensitive_clauses else 0
        sensitive_rule = "含竞业限制/排他条款等敏感条款" if validated.has_sensitive_clauses else "未包含敏感条款"
        breakdown.append({"name": "敏感条款", "score": sensitive_score, "max": 20, "detail": sensitive_rule})

        # 总分
        total = amount_score + pattern_score + sensitive_score
        total = max(0, min(total, 100))

        if total >= 80:
            level = "HIGH"
            advice = "高风险，触发人工审批流程。系统将挂起当前审批节点，等待管理员确认。"
        elif total >= 50:
            level = "MEDIUM"
            advice = "中风险，系统自动通过但建议人工复核。请关注不一致字段和法律依据。"
        else:
            level = "LOW"
            advice = "低风险，系统自动通过。合同内容基本合规，无需人工干预。"

        return {
            "score": round(total, 1),
            "level": level,
            "advice": advice,
            "breakdown": [{"name": b["name"], "score": b["score"], "max": b["max"], "detail": b["detail"]} for b in breakdown],
            "factors": {
                "amount": validated.contract_amount,
                "mismatches": validated.mismatch_count,
                "citations": validated.citation_count,
                "sensitive": validated.has_sensitive_clauses,
            },
            "citation_info": cite_rule,
            "requires_approval": level == "HIGH",
        }


class SuspendNodeInput(BaseModel):
    node_id: str = Field(description="挂起的审批节点 ID")
    reason: str = Field(description="挂起原因")
    timeout: int = Field(default=300, description="超时秒数")


class SuspendNodeTool(BaseTool):
    name = "suspend_node"
    description = "挂起敏感审批节点，SSE 推送人工审批请求，超时自动拒绝"
    input_schema = SuspendNodeInput
    require_approval = True

    async def _run(self, validated: SuspendNodeInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        # TODO: SSE 推送审批请求
        return {
            "node_id": validated.node_id,
            "status": "pending",
            "reason": validated.reason,
            "timeout": validated.timeout,
            "message": f"节点 {validated.node_id} 已挂起，等待人工审批。超时 {validated.timeout}s 自动拒绝。",
        }


class ApproveNodeInput(BaseModel):
    node_id: str = Field(description="要批准的节点 ID")
    reviewer: str = Field(default="", description="审批人")
    comment: str = Field(default="", description="审批意见")


class ApproveNodeTool(BaseTool):
    name = "approve_node"
    description = "人工确认通过审批节点"
    input_schema = ApproveNodeInput

    async def _run(self, validated: ApproveNodeInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        return {
            "node_id": validated.node_id,
            "decision": PermissionDecision.ALLOW.value,
            "reviewer": validated.reviewer,
            "comment": validated.comment,
            "timestamp": call.timestamp.isoformat(),
        }


class GenerateReportInput(BaseModel):
    task_id: str = Field(description="审批任务 ID")
    sections: list[str] = Field(default_factory=lambda: [
        "summary", "field_comparison", "compliance_review", "risk_assessment", "recommendation"
    ])


class GenerateReportTool(BaseTool):
    name = "generate_report"
    description = "生成结构化审批报告"
    input_schema = GenerateReportInput

    async def _run(self, validated: GenerateReportInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        """从 context 中汇总各阶段结果，生成报告"""
        ctx = kwargs.get("context", {})
        return {
            "task_id": validated.task_id,
            "sections": validated.sections,
            "data": {
                "extract": ctx.get("extract_fields", {}),
                "comply": ctx.get("_citations", []),
                "risk": ctx.get("_risk_data", {}),
            },
        }
