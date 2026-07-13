"""
新 Agent 体系: 先结构化→再模式识别→后法条解释→最后评分
ContractParsing → ObligationMatrix → RiskPattern(规则) → LegalCitation → Evidence → RiskDecision
"""
from typing import Any, Dict
from .base_agent import BaseAgent
from ..models.schemas import ApprovalTask, ToolResult


class InvestigationAgent(BaseAgent):
    """合同解析 + 义务矩阵 Agent"""
    agent_type = "investigation"

    async def setup(self, task, context):
        from ..tools.registry import registry
        self.tools = registry

    async def think(self, context):
        task = context.get("task")
        ocr = (task.user_input or {}).get("_ocr_data", {}) if task else {}
        full_text = ocr.get("full_text", "") if isinstance(ocr, dict) else ""
        if not full_text:
            ui = {k: v for k, v in (task.user_input or {}).items() if not k.startswith('_')}
            full_text = "\n".join([f"{k}: {v}" for k, v in ui.items()]) if ui else ""
        return f"解析合同，文本长度: {len(full_text)}"

    async def plan(self, thought, context):
        task = context.get("task")
        ocr = (task.user_input or {}).get("_ocr_data", {}) if task else {}
        full_text = ocr.get("full_text", "") if isinstance(ocr, dict) else ""
        if not full_text:
            ui = {k: v for k, v in (task.user_input or {}).items() if not k.startswith('_')}
            full_text = "\n".join([f"{k}: {v}" for k, v in ui.items()]) if ui else ""
        if not context.get("_full_text"):
            context["_full_text"] = full_text
        return ("build_obligation_matrix", {"full_text": full_text, "clauses": []})

    async def observe(self, result: ToolResult, context):
        if result.success and result.data:
            context["_obligation_matrix"] = result.data.get("matrix", [])
            context["_balance"] = result.data.get("summary", {})
            return f"矩阵构建完成，权责平衡度: {context['_balance'].get('rights_obligations_balance','unknown')}"
        return f"矩阵构建失败: {result.error}"

    async def teardown(self, result, context):
        return {"matrix": context.get("_obligation_matrix", []), "balance": context.get("_balance", {})}


class RiskPatternAgent(BaseAgent):
    """风险模式扫描 Agent — 规则优先"""
    agent_type = "risk_pattern"

    async def setup(self, task, context):
        from ..tools.registry import registry
        self.tools = registry

    async def think(self, context):
        return f"扫描风险模式..."

    async def plan(self, thought, context):
        return ("scan_risk_patterns", {
            "full_text": context.get("_full_text", ""),
            "clauses": [],
            "obligation_matrix": context.get("_balance", {}),
        })

    async def observe(self, result: ToolResult, context):
        if result.success and result.data:
            context["_risk_patterns"] = result.data.get("matched_patterns", [])
            context["_critical_count"] = result.data.get("critical_count", 0)
            context["_high_count"] = result.data.get("high_count", 0)
            return f"模式扫描: {context['_critical_count']} CRITICAL + {context['_high_count']} HIGH"
        return f"模式扫描失败: {result.error}"

    async def teardown(self, result, context):
        return {"patterns": context.get("_risk_patterns", []),
                "critical": context.get("_critical_count", 0),
                "high": context.get("_high_count", 0)}


class LegalCitationAgent(BaseAgent):
    """法条映射 Agent — 风险→法条→解释（不是发现风险，而是解释已有风险）"""
    agent_type = "legal"

    async def setup(self, task, context):
        from ..tools.registry import registry
        self.tools = registry
        context["_legal_done"] = []

    async def think(self, context):
        patterns = context.get("_risk_patterns", [])
        done = len(context.get("_legal_done", []))
        if not patterns: return "无风险点需要法条映射。"
        return f"法条映射: {len(patterns)} 风险点, 已完成 {done}"

    async def plan(self, thought, context):
        task = context.get("task")
        patterns = context.get("_risk_patterns", [])
        if not patterns:
            return ("search_law", {"contract_type": task.contract_type if task else "service",
                    "keywords": ["违约责任", "付款条件", "合同解除", "免责条款", "履行原则"]})
        done = set(context.get("_legal_done", []))
        for p in patterns:
            pid = p.get("pattern_id", "")
            if pid not in done:
                keywords = [p.get("category", ""), p.get("explanation", "")[:30]]
                return ("search_law", {"contract_type": task.contract_type if task else "purchase", "keywords": keywords + ["违约责任", "公平原则", "合同解除"]})
        return None, None

    async def observe(self, result: ToolResult, context):
        if result.success and result.data:
            if "clauses" in result.data:
                context["_citations"] = result.data["clauses"]
                return f"检索到 {len(result.data['clauses'])} 条相关法条"
        return f"法条检索失败: {result.error}"

    async def teardown(self, result, context):
        return {"citations": context.get("_citations", []),
                "risk_patterns": context.get("_risk_patterns", []),
                "balance": context.get("_balance", {})}


class EvidenceAgent(BaseAgent):
    """证据生成 Agent — 为前端提供原文证据+标注+建议"""
    agent_type = "evidence"

    async def setup(self, task, context):
        from ..tools.registry import registry
        self.tools = registry

    async def think(self, context):
        patterns = context.get("_risk_patterns", [])
        return f"生成证据: {len(patterns)} 风险点"

    async def plan(self, thought, context):
        ocr = (context.get("task", {}).user_input or {}).get("_ocr_data", {}) if context.get("task") else {}
        positions = ocr.get("positions", []) if isinstance(ocr, dict) else []
        return ("generate_evidence", {
            "risks": context.get("_risk_patterns", []),
            "full_text": context.get("_full_text", ""),
            "positions": positions,
        })

    async def observe(self, result: ToolResult, context):
        if result.success and result.data:
            context["_evidences"] = result.data.get("evidences", [])
            return f"证据生成完成: {len(context['_evidences'])} 条"
        return f"证据生成失败: {result.error}"

    async def teardown(self, result, context):
        return {"evidences": context.get("_evidences", [])}


class RiskDecisionAgent(BaseAgent):
    """风险决策 Agent — 多维评分 + 强制升级"""
    agent_type = "risk"

    async def setup(self, task, context):
        from ..tools.registry import registry
        self.tools = registry

    async def think(self, context):
        critical = context.get("_critical_count", 0)
        high = context.get("_high_count", 0)
        return f"风险决策: {critical} CRITICAL + {high} HIGH"

    async def plan(self, thought, context):
        task = context.get("task")
        amt = 0
        try: amt = float(str((task.user_input or {}).get("amount", "0")).replace(",", "").replace("元", "").strip())
        except: pass
        critical = context.get("_critical_count", 0)
        balance = context.get("_balance", {})
        imbalance_score = balance.get("imbalance_score", 0) if isinstance(balance, dict) else 0
        # 强制升级规则
        forced_level = None
        if critical >= 5: forced_level = "CRITICAL"
        elif critical >= 3: forced_level = "HIGH"
        elif critical >= 1: forced_level = "MEDIUM"
        has_sensitive = critical >= 2 or imbalance_score > 80
        return ("risk_score", {
            "mismatch_count": critical + context.get("_high_count", 0),
            "citation_count": len(context.get("_citations", [])),
            "contract_amount": amt,
            "has_sensitive_clauses": has_sensitive,
        })

    async def observe(self, result: ToolResult, context):
        if result.success and result.data:
            # 强制升级
            data = dict(result.data)
            critical = context.get("_critical_count", 0)
            if critical >= 5 and data.get("level") not in ("CRITICAL", "HIGH"):
                data["level"] = "CRITICAL"
                data["score"] = max(data.get("score", 0), 95)
            elif critical >= 3 and data.get("level") == "LOW":
                data["level"] = "HIGH"
                data["score"] = max(data.get("score", 0), 80)
            elif critical >= 1 and data.get("level") == "LOW":
                data["level"] = "MEDIUM"
                data["score"] = max(data.get("score", 0), 55)
            context["_risk_data"] = data
            return f"最终决策: {data['score']}分/{data['level']}(强制升级: {critical} CRITICAL)"
        return f"决策失败: {result.error}"

    async def teardown(self, result, context):
        data = context.get("_risk_data", {})
        return {"score": data.get("score", 0), "level": data.get("level", "LOW"),
                "breakdown": data.get("breakdown", []), "advice": data.get("advice", ""),
                "critical_count": context.get("_critical_count", 0)}
