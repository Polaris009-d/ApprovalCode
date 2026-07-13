"""
高级推理工具 — 法律论证 + 事实调查 + 对抗验证
"""
import json, httpx
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from ..base_tool import BaseTool
from ...models.schemas import ToolCall
from ...config import settings


# ═══════════════ 事实调查工具 ═══════════════

class InvestigateFactsInput(BaseModel):
    contract_text: str = Field(description="合同全文/OCR文字")
    ocr_fields: dict = Field(default_factory=dict, description="OCR提取的结构化字段")


class InvestigateFactsTool(BaseTool):
    name = "investigate_facts"
    description = "从合同文本中提取结构化事实，含隐含风险指标（如付款间隔、违约金占比）"
    input_schema = InvestigateFactsInput

    async def _run(self, validated: InvestigateFactsInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        if not settings.LLM_API_KEY:
            return {"facts": [], "indicators": {}}
        prompt = f"""你是合同审查的事实调查员。从以下合同文本提取结构化事实和隐含风险指标。
合同文本: {validated.contract_text[:3000]}

返回JSON:
{{
  "facts": [
    {{"key": "付款条款", "value": "按季度支付，共4期，每期21500元", "risk_flag": false}},
    {{"key": "违约金", "value": "总金额10%", "risk_flag": true, "risk_reason": "未设上限"}}
  ],
  "indicators": {{
    "first_payment_gap_days": 9,
    "penalty_ratio": 10,
    "has_termination_clause": false,
    "has_force_majeure": false
  }}
}}
只返回JSON。"""
        return await _call_llm(prompt, {"facts": [], "indicators": {}})


# ═══════════════ 三段论论证工具 ═══════════════

class ConstructArgumentInput(BaseModel):
    clause: dict = Field(description="法律条文 {id, title, content}")
    facts: list = Field(default_factory=list, description="调查事实列表")
    contract_fields: dict = Field(default_factory=dict)


class ConstructArgumentTool(BaseTool):
    name = "construct_argument"
    description = "模拟律师三段论推理: 大前提(法律)→小前提(事实)→结论(风险判断)"
    input_schema = ConstructArgumentInput

    async def _run(self, validated: ConstructArgumentInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        if not settings.LLM_API_KEY:
            return {"premise_major": validated.clause.get("content", ""), "premise_minor": "", "conclusion": "", "risk_level": "LOW"}
        prompt = f"""你是律师。根据法律条文和合同事实进行三段论推理。

法律条文: {validated.clause.get('id')} - {validated.clause.get('title')}
条文内容: {validated.clause.get('content')}

合同事实: {json.dumps(validated.facts, ensure_ascii=False)}
合同字段: {json.dumps(validated.contract_fields, ensure_ascii=False)}

返回JSON:
{{
  "premise_major": "大前提(法律规定)",
  "premise_minor": "小前提(合同事实)",
  "conclusion": "结论(该合同在此条文下的风险)",
  "risk_level": "HIGH/MEDIUM/LOW",
  "violation": true/false,
  "risk_detail": "1-2句话风险说明",
  "suggestion": "修改建议"
}}
只返回JSON。"""
        return await _call_llm(prompt, {"premise_major": "", "premise_minor": "", "conclusion": "", "risk_level": "LOW", "violation": False})


# ═══════════════ 对抗验证工具 ═══════════════

class AdversarialReviewInput(BaseModel):
    argument: dict = Field(description="待反驳的论证 {premise_major, premise_minor, conclusion}")


class AdversarialReviewTool(BaseTool):
    name = "adversarial_review"
    description = "尝试反驳论证，只有经得起挑战的论证才输出(参考Claude Code verify模式)"
    input_schema = AdversarialReviewInput

    async def _run(self, validated: AdversarialReviewInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        if not settings.LLM_API_KEY:
            return {"refuted": False, "refute_reason": ""}
        prompt = f"""你是一名资深律师，尝试反驳以下法律论证。如果论证有漏洞，请指出。

论证内容: {json.dumps(validated.argument, ensure_ascii=False)}

返回JSON:
{{
  "refuted": true/false,
  "refute_reason": "反驳理由(如果refuted=true)",
  "confidence": "论证的可信度 HIGH/MEDIUM/LOW"
}}
只返回JSON。"""
        return await _call_llm(prompt, {"refuted": False, "refute_reason": "", "confidence": "HIGH"})


# ═══════════════ 协商建议工具 ═══════════════

class NegotiateInput(BaseModel):
    risk: dict = Field(description="风险点 {title, detail, risk_level}")


class NegotiateTool(BaseTool):
    name = "negotiate_suggestions"
    description = "对每个风险点生成多个谈判方案(保守/平衡/激进)，标注利弊"
    input_schema = NegotiateInput

    async def _run(self, validated: NegotiateInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        if not settings.LLM_API_KEY:
            return {"options": []}
        prompt = f"""你是合同谈判专家。对以下风险点给出3个谈判方案。

风险: {json.dumps(validated.risk, ensure_ascii=False)}

返回JSON:
{{
  "options": [
    {{"strategy": "保守", "action": "具体措施", "pros": "优点", "cons": "缺点"}},
    {{"strategy": "平衡", "action": "具体措施", "pros": "优点", "cons": "缺点"}},
    {{"strategy": "激进", "action": "具体措施", "pros": "优点", "cons": "缺点"}}
  ],
  "recommendation": "推荐方案及理由"
}}
只返回JSON。"""
        return await _call_llm(prompt, {"options": []})


# ═══════════════ 财务分析工具 ═══════════════

class FinancialAnalysisInput(BaseModel):
    amount: float = Field(default=0)
    payment_period: str = Field(default="")
    payment_method: str = Field(default="")
    contract_type: str = Field(default="purchase")


class FinancialAnalysisTool(BaseTool):
    name = "financial_analysis"
    description = "财务条款健康度分析: 付款周期、现金流影响、风险传导"
    input_schema = FinancialAnalysisInput

    async def _run(self, validated: FinancialAnalysisInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        findings = []
        if validated.amount > 100000:
            findings.append({"type": "金额预警", "detail": f"{validated.amount}元超过10万，需财务总监审批", "severity": "MEDIUM"})
        if validated.amount <= 100000:
            findings.append({"type": "金额合规", "detail": f"{validated.amount}元在10万以内，无需招标", "severity": "LOW"})

        if validated.payment_period:
            if "季度" in validated.payment_period or "4期" in validated.payment_period:
                findings.append({"type": "付款周期", "detail": "按季度支付，分摊合理，现金流压力可控", "severity": "LOW"})
            elif "一次性" in validated.payment_period:
                findings.append({"type": "付款周期", "detail": "一次性付清，现金流压力集中", "severity": "MEDIUM"})

        if validated.payment_method and "银行转账" in validated.payment_method:
            findings.append({"type": "支付方式", "detail": "银行转账，合规安全", "severity": "LOW"})

        return {"findings": findings, "propagation_chain": [], "overall_health": "GOOD" if len([f for f in findings if f["severity"] == "HIGH"]) == 0 else "WARNING"}


# ═══════════════ 对抗性辩论工具 ═══════════════

class AdversarialDebateInput(BaseModel):
    clause: dict = Field(description="法律条文 {id, title, content, first_principles, relationships}")
    contract_facts: list = Field(default_factory=list)
    contract_fields: dict = Field(default_factory=dict)


class PlaintiffAgentTool(BaseTool):
    """原告律师 — 论证合同存在风险"""
    name = "plaintiff_argue"
    description = "以原告律师身份论证合同存在法律风险，找出所有可能的违规点"
    input_schema = AdversarialDebateInput

    async def _run(self, validated: AdversarialDebateInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        prompt = f"""你是原告律师，受客户委托审查合同风险。你需要找出合同中所有可能违反法律的条款。

法律条文: {validated.clause.get('id')} {validated.clause.get('title')}
条文内容: {validated.clause.get('content')}
第一性原理: {validated.clause.get('first_principles', '')}
关联法条: {json.dumps(validated.clause.get('relationships', []), ensure_ascii=False)}
合同事实: {json.dumps(validated.contract_facts, ensure_ascii=False)}
合同字段: {json.dumps(validated.contract_fields, ensure_ascii=False)}

你需要以最激进的原告立场，找出所有可能的违规点和风险。返回JSON:
{{"arguments":[{{"claim":"主张","legal_basis":"法律依据","reasoning":"推理过程","risk_level":"HIGH/MEDIUM/LOW"}}],"severity":"整体风险等级"}}
只返回JSON。"""
        return await _call_llm(prompt, {"arguments": [], "severity": "LOW"})


class DefendantAgentTool(BaseTool):
    """被告律师 — 为合同辩护"""
    name = "defendant_defend"
    description = "以被告律师身份为合同条款辩护，找出合理性和合规依据"
    input_schema = AdversarialDebateInput

    async def _run(self, validated: AdversarialDebateInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        prompt = f"""你是被告律师，需要为这份合同的条款辩护。解释为什么合同条款是合理和合法的。

法律条文: {validated.clause.get('id')} {validated.clause.get('title')}
条文内容: {validated.clause.get('content')}
第一性原理: {validated.clause.get('first_principles', '')}
关联法条: {json.dumps(validated.clause.get('relationships', []), ensure_ascii=False)}
合同事实: {json.dumps(validated.contract_facts, ensure_ascii=False)}
合同字段: {json.dumps(validated.contract_fields, ensure_ascii=False)}

你需要为合同辩护，说明为什么这些条款合理合法。返回JSON:
{{"defenses":[{{"point":"辩护点","legal_basis":"法律依据","reasoning":"推理过程","strength":"STRONG/MEDIUM/WEAK"}}],"overall_assessment":"总体评估"}}
只返回JSON。"""
        return await _call_llm(prompt, {"defenses": [], "overall_assessment": ""})


class JudgeInput(BaseModel):
    plaintiff_args: list = Field(default_factory=list)
    defendant_args: list = Field(default_factory=list)
    clause: dict = Field(default_factory=dict)

class JudgeAgentTool(BaseTool):
    """法官 — 裁决"""
    name = "judge_rule"
    description = "以法官身份权衡原告和被告论点，做出公正裁决"
    input_schema = JudgeInput

    async def _run(self, validated: JudgeInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        prompt = f"""你是法官。权衡原告和被告的论点，做出公正裁决。
原告主张: {json.dumps(validated.plaintiff_args, ensure_ascii=False)}
被告辩护: {json.dumps(validated.defendant_args, ensure_ascii=False)}
适用法条: {validated.clause.get('id', '') if isinstance(validated.clause, dict) else ''}
返回JSON: {{"verdict":"判决结果","reasoning":"法官推理","risk_finding":"HIGH/MEDIUM/LOW","plaintiff_wins":["采纳原告观点"],"defendant_wins":["采纳被告观点"],"final_advice":"最终建议"}}
只返回JSON。"""
        return await _call_llm(prompt, {"verdict": "", "reasoning": "", "risk_finding": "LOW", "final_advice": ""})


# ═══════════════ LLM Helper ═══════════════

async def _call_llm(prompt: str, fallback: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"},
                json={"model": settings.LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 800, "temperature": 0.1},
            )
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"].strip()
                for tag in ["```json", "```"]:
                    if tag in raw: raw = raw.split(tag, 1)[-1]
                if raw.endswith("```"): raw = raw[:-3]
                return json.loads(raw.strip())
    except Exception as e:
        print(f"[LLM] {e}")
    return fallback
