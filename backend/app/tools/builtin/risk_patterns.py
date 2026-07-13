"""
风险模式库 — 确定性规则 + LLM 语义分类
先规则命中，再 LLM 解释
"""
import json, re
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from ..base_tool import BaseTool
from ...models.schemas import ToolCall
from ...config import settings


# ═══════════════ 高风险模式库(规则引擎) ═══════════════

CRITICAL_PATTERNS = [
    {"id": "PAYMENT_INDEFINITE_EXTENSION", "severity": "CRITICAL", "category": "付款",
     "keywords": ["无限期顺延", "无限期延期", "无限期推迟", "内部流程.*不算违约", "有权.*顺延付款", "无限期.*付款"],
     "explanation": "付款期限不确定，甲方可无限期延期付款且免责，乙方回款完全不可控"},
    {"id": "BUYER_NON_PAYMENT_EXEMPTION", "severity": "CRITICAL", "category": "付款",
     "keywords": ["不付款.*不算违约", "暂缓支付.*不算违约", "甲方不付款.*不承担", "逾期付款.*免责"],
     "explanation": "甲方付款义务被免责，违反合同法基本公平原则"},
    {"id": "INVOICE_BEFORE_PAYMENT_TRAP", "severity": "CRITICAL", "category": "付款",
     "keywords": ["先开.*全额发票.*否则.*拒绝付款", "先开票.*否则.*永久拒付", "先开具发票.*否则.*不付款"],
     "explanation": "乙方必须先开票承担税负，甲方却可无限期不付款，形成资金占用陷阱"},
    {"id": "UNILATERAL_ACCEPTANCE_ORAL", "severity": "CRITICAL", "category": "验收",
     "keywords": ["验收标准.*口头", "验收.*由.*说了算", "无书面.*验收标准", "口头.*决定.*验收"],
     "explanation": "验收标准由甲方单方口头决定，乙方无客观标准可依"},
    {"id": "UNILATERAL_TERMINATION_NO_COMPENSATION", "severity": "CRITICAL", "category": "解约",
     "keywords": ["无理由.*随时解除", "可.*随时.*解除.*合同", "不赔偿.*不补偿.*不担责",
                  "解除合同.*不承担.*责任", "无理由解除.*不赔偿"],
     "explanation": "甲方可无理由随时解除合同且不承担任何责任，乙方无对等权利"},
    {"id": "RIGHTS_OBLIGATIONS_SEVERE_IMBALANCE", "severity": "CRITICAL", "category": "权责",
     "keywords": [],  # 由 Obligation Matrix 计算
     "explanation": "合同权利义务严重失衡"},
]

HIGH_PATTERNS = [
    {"id": "EXCESSIVE_LATE_PENALTY", "severity": "HIGH", "category": "交货",
     "keywords": ["晚.*分钟.*扣.*%", "晚.*小时.*解除", "晚.*小时.*赔偿.*%", "迟延.*分钟.*%"],
     "explanation": "延期处罚触发条件过于苛刻，与实际损失不成比例"},
    {"id": "SUPER_LONG_PAYMENT_TERM", "severity": "HIGH", "category": "付款",
     "keywords": ["\\d{2,3}.*自然日.*审核", "\\d{2,3}.*工作日.*支付", "验收.*后.*\\d{2,3}.*天.*付款"],
     "explanation": "付款周期过长，乙方回款周期超90天"},
    {"id": "QUALITY_UNLIMITED_LIABILITY", "severity": "HIGH", "category": "质量",
     "keywords": ["无论使用多久.*质量问题", "随时.*主张.*质量", "无限.*期.*质量.*责任",
                  "全额退款.*双倍赔偿", "使用.*之后.*仍.*质量问题"],
     "explanation": "质量责任期限无限延长，乙方承担过度赔偿"},
    {"id": "LIABILITY_AFTER_DELIVERY_ON_SUPPLIER", "severity": "HIGH", "category": "责任",
     "keywords": ["交付后.*一切.*责任.*乙方", "交付后.*仍.*由.*乙方", "交付.*之后.*责任.*乙方"],
     "explanation": "货物交付后风险仍由乙方承担，违反风险随交付转移原则"},
    {"id": "DISPUTE_UNFAIR_FORUM", "severity": "HIGH", "category": "争议",
     "keywords": ["指定.*外地.*仲裁", "只能.*甲方.*指定.*仲裁", "到甲方.*所在地.*仲裁"],
     "explanation": "争议解决地点由甲方指定，增加乙方维权成本"},
    {"id": "DISPUTE_ALL_COSTS_ON_SUPPLIER", "severity": "HIGH", "category": "争议",
     "keywords": ["乙方.*承担.*全部.*费用", "所有.*费用.*由.*乙方", "费用.*乙方.*承担"],
     "explanation": "争议解决费用全部由乙方承担"},
    {"id": "NO_PREPAYMENT_RISK", "severity": "HIGH", "category": "付款",
     "keywords": ["不支付.*预付款", "无.*预付款", "不付.*预付款"],
     "explanation": "零预付款意味着乙方需垫付全部成本"},
]


# ═══════════════ Risk Pattern Tool ═══════════════

class ScanRiskPatternsInput(BaseModel):
    full_text: str = Field(default="", description="合同全文")
    clauses: list = Field(default_factory=list, description="结构化条款列表")
    obligation_matrix: dict = Field(default_factory=dict, description="权利义务矩阵(E键矩阵Agent输出)")


class ScanRiskPatternsTool(BaseTool):
    """风险模式扫描 — 先规则命中，再 LLM 补充"""
    name = "scan_risk_patterns"
    description = "先确定性规则扫描高风险模式，再用LLM语义补充"
    input_schema = ScanRiskPatternsInput

    async def _run(self, validated: ScanRiskPatternsInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        text = validated.full_text
        matched = []

        # Phase 1: 确定性规则扫描
        for pattern in CRITICAL_PATTERNS + HIGH_PATTERNS:
            for kw in pattern["keywords"]:
                if re.search(kw, text):
                    matched.append({
                        "pattern_id": pattern["id"],
                        "severity": pattern["severity"],
                        "category": pattern["category"],
                        "matched_keyword": kw,
                        "explanation": pattern["explanation"],
                        "source": "rule",
                    })
                    break  # 一个模式只记录一次

        # Phase 2: 从义务矩阵提取失衡指标
        matrix = validated.obligation_matrix
        if isinstance(matrix, dict) and matrix:
            imbalance = matrix.get("rights_obligations_balance", "")
            if imbalance in ("severely_unbalanced", "highly_unbalanced"):
                matched.append({
                    "pattern_id": "RIGHTS_OBLIGATIONS_SEVERE_IMBALANCE",
                    "severity": "CRITICAL",
                    "category": "权责",
                    "matched_keyword": imbalance,
                    "explanation": f"权责失衡度: {imbalance}，买方权利{matrix.get('buyer_rights_count',0)}项，卖方义务{matrix.get('supplier_obligations_count',0)}项",
                    "source": "matrix",
                })

        # Phase 3: LLM 语义补充(只对规则没命中的条款)
        if settings.LLM_API_KEY:
            llm_found = await self._llm_scan(text, matched)
            matched.extend(llm_found)

        critical_count = sum(1 for m in matched if m["severity"] == "CRITICAL")
        high_count = sum(1 for m in matched if m["severity"] == "HIGH")
        return {
            "matched_patterns": matched,
            "critical_count": critical_count,
            "high_count": high_count,
            "total_risk_count": len(matched),
        }

    async def _llm_scan(self, text: str, already_matched: list) -> list:
        existing_ids = {m["pattern_id"] for m in already_matched}
        prompt = f"""扫描以下合同条款，找出规则引擎未命中的风险模式。只返回规则尚未发现的模式。

已命中: {json.dumps(list(existing_ids), ensure_ascii=False)}

合同内容:
{text[:3000]}

返回JSON数组(只针对规则引擎漏掉的风险):
[{{"pattern_id":"自定义ID","severity":"CRITICAL/HIGH/MEDIUM","category":"分类","explanation":"风险说明","evidence":"原文证据"}}]

如果没有新发现，返回空数组[]。只返回JSON。"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{settings.LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"},
                    json={"model": settings.LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000, "temperature": 0.1},
                )
                if resp.status_code == 200:
                    raw = resp.json()["choices"][0]["message"]["content"].strip()
                    for tag in ["```json", "```"]:
                        if tag in raw: raw = raw.split(tag, 1)[-1]
                    if raw.endswith("```"): raw = raw[:-3]
                    items = json.loads(raw.strip())
                    for item in items:
                        item["source"] = "llm"
                    return items
        except: pass
        return []


# ═══════════════ Obligation Matrix Tool ═══════════════

class BuildObligationMatrixInput(BaseModel):
    full_text: str = Field(default="")
    clauses: list = Field(default_factory=list)


class BuildObligationMatrixTool(BaseTool):
    """构建权利义务矩阵"""
    name = "build_obligation_matrix"
    description = "将合同条款拆解为权利/义务矩阵，检测权责失衡"
    input_schema = BuildObligationMatrixInput

    async def _run(self, validated: BuildObligationMatrixInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        if not settings.LLM_API_KEY:
            return {"matrix": [], "balance": "unknown"}
        prompt = f"""分析以下合同的权利义务矩阵。

合同内容:
{validated.full_text[:4000]}

返回JSON:
{{
  "matrix": [
    {{"clause_category":"付款/交货/验收/质量/责任/解约/争议","party_burdened":"乙方/甲方","party_benefited":"甲方/乙方","obligation_type":"付款义务/交货义务/...,"risk_flag":true/false,"detail":"简述"}}
  ],
  "summary": {{
    "buyer_rights_count": 0,
    "buyer_obligations_count": 0,
    "supplier_obligations_count": 0,
    "supplier_protections_count": 0,
    "rights_obligations_balance": "balanced/unbalanced/severely_unbalanced",
    "imbalance_score": 0
  }}
}}
只返回JSON。"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    f"{settings.LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"},
                    json={"model": settings.LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1500, "temperature": 0},
                )
                if resp.status_code == 200:
                    raw = resp.json()["choices"][0]["message"]["content"].strip()
                    for tag in ["```json", "```"]:
                        if tag in raw: raw = raw.split(tag, 1)[-1]
                    if raw.endswith("```"): raw = raw[:-3]
                    return json.loads(raw.strip())
        except: pass
        return {"matrix": [], "summary": {"rights_obligations_balance": "unknown", "imbalance_score": 0}}


# ═══════════════ Evidence Agent Tool ═══════════════

class GenerateEvidenceInput(BaseModel):
    risks: list = Field(default_factory=list, description="风险模式列表")
    full_text: str = Field(default="")
    positions: list = Field(default_factory=list, description="OCR位置数据")


class GenerateEvidenceTool(BaseTool):
    """生成前端可展示的证据"""
    name = "generate_evidence"
    description = "为每个风险点生成原文证据、解释、建议和置信度"
    input_schema = GenerateEvidenceInput

    async def _run(self, validated: GenerateEvidenceInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        evidence_list = []
        for i, risk in enumerate(validated.risks):
            ev = {
                "risk_id": f"RISK_{i+1:03d}",
                "pattern_id": risk.get("pattern_id", ""),
                "severity": risk.get("severity", "MEDIUM"),
                "category": risk.get("category", ""),
                "explanation": risk.get("explanation", ""),
                "evidence_text": risk.get("matched_keyword", risk.get("evidence", "")),
                "confidence": 0.95 if risk.get("source") == "rule" else 0.80,
            }
            # 匹配 OCR 位置
            for pos in validated.positions:
                if ev["evidence_text"][:6] in pos.get("text", ""):
                    ev["position"] = {"top": pos["top"], "left": pos["left"], "width": pos["width"], "height": pos["height"]}
                    break
            evidence_list.append(ev)
        return {"evidences": evidence_list, "total": len(evidence_list)}
