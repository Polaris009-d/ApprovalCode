"""
MasterAgent — Phase 0→1→2→3→4→5 编排
Phase 0: Investigation(Obligation Matrix) → Phase 1: Risk Pattern(规则优先) → Phase 2: Legal Citation(法条映射)
→ Phase 3: Evidence(证据生成) → Phase 4: Risk Decision(多维评分+强制升级)
"""
import asyncio, time, json
from typing import Any, Dict, Optional

from .base_agent import BaseAgent
from .sub_agents import (InvestigationAgent, RiskPatternAgent,
    LegalCitationAgent, EvidenceAgent, RiskDecisionAgent)
from ..models.schemas import AgentStatus, ApprovalTask, ApprovalReport, ReActStepType
from ..tools.registry import ToolRegistry
from ..security.rule_engine import RuleEngine
from ..memory.short_term import ShortTermMemory
from ..observability.audit import AuditLogger


class MasterAgent(BaseAgent):
    agent_type = "master"

    def __init__(self, tools: ToolRegistry, memory: ShortTermMemory,
                 rule_engine: RuleEngine, audit: AuditLogger, reasoning=None):
        super().__init__()
        self.tools = tools; self.memory = memory; self.rule_engine = rule_engine; self.audit = audit
        self.subagent_results: Dict[str, Any] = {}
        self.subagents = {
            "investigation": InvestigationAgent(),
            "risk_pattern": RiskPatternAgent(),
            "legal": LegalCitationAgent(),
            "evidence": EvidenceAgent(),
            "risk": RiskDecisionAgent(),
        }

    async def setup(self, task, context):
        context["task"] = task; context["start_time"] = time.perf_counter()
        await self.audit.log_event("task_start", {"task_id": task.task_id})

    async def think(self, context):
        c = context.get("completed_phases", [])
        if "investigation" not in c: return "Phase 0: 合同解析+义务矩阵。"
        if "risk_pattern" not in c: return "Phase 1: 风险模式扫描(规则优先)。"
        if "legal" not in c: return "Phase 2: 法条映射。"
        if "evidence" not in c: return "Phase 3: 证据生成。"
        if "risk" not in c: return "Phase 4: 风险决策+强制升级。"
        return "完成。"

    async def plan(self, thought, context):
        c = context.get("completed_phases", [])
        phases = [("investigation","investigation"),("risk_pattern","risk_pattern"),
                  ("legal","legal"),("evidence","evidence"),("risk","risk")]
        for phase_key, agent_name in phases:
            if phase_key not in c: return ("dispatch_subagent", {"agent": agent_name})
        return None, None

    async def act_and_observe(self, step_num, plan, context):
        tool_name, tool_args = self._parse_plan(plan)
        if tool_name is None: return True, context
        if tool_name == "dispatch_subagent":
            agent_name = tool_args.get("agent")
            done, result = await self._dispatch_subagent(step_num, tool_args, context)
            await self._observe_dispatch(result, context)
            if not done: context.setdefault("completed_phases", []).append(agent_name)
            return done, result
        return await super().act_and_observe(step_num, plan, context)

    async def _dispatch_subagent(self, step_num, args, context):
        agent_name = args.get("agent")
        sub = self.subagents.get(agent_name)
        if sub is None: return True, {"error": f"Unknown: {agent_name}"}
        self._record_step(step_num, ReActStepType.ACT, content=f"dispatch {agent_name}")
        try:
            result, sub_trace = await asyncio.wait_for(sub.execute(context["task"], context), timeout=self.timeout)
            self.trace.extend(sub_trace)
            self._record_step(step_num + 1, ReActStepType.OBSERVE, content=f"{agent_name} done")
            return False, {"agent": agent_name, "data": result}
        except asyncio.TimeoutError:
            sub.cancel(); return True, {"error": f"{agent_name} timeout"}

    async def _observe_dispatch(self, dispatch_result, context):
        if isinstance(dispatch_result, dict) and dispatch_result.get("agent"):
            self.subagent_results[dispatch_result["agent"]] = dispatch_result.get("data", {})

    async def observe(self, result, context):
        if isinstance(result, dict) and result.get("agent"):
            self.subagent_results[result["agent"]] = result.get("data", {})
        return ""

    def _parse_plan(self, plan):
        if isinstance(plan, tuple) and len(plan) == 2: return plan[0], plan[1]
        return None, None

    async def teardown(self, result, context):
        total_ms = (time.perf_counter() - context["start_time"]) * 1000
        risk = self.subagent_results.get("risk", {})
        legal = self.subagent_results.get("legal", {})
        patterns = self.subagent_results.get("risk_pattern", {})
        evidence = self.subagent_results.get("evidence", {})
        investigation = self.subagent_results.get("investigation", {})

        risk_score_val = risk.get("score", 0) if isinstance(risk, dict) else 0
        risk_level_val = risk.get("level", "LOW") if isinstance(risk, dict) else "LOW"
        citations = legal.get("citations", []) if isinstance(legal, dict) else []
        risk_patterns = patterns.get("patterns", []) if isinstance(patterns, dict) else []
        evidences = evidence.get("evidences", []) if isinstance(evidence, dict) else []
        balance = investigation.get("balance", {}) if isinstance(investigation, dict) else {}
        critical_count = risk.get("critical_count", patterns.get("critical", 0)) if isinstance(risk, dict) else (patterns.get("critical", 0) if isinstance(patterns, dict) else 0)

        ct_map = {"purchase": "采购", "service": "服务", "lease": "租赁", "labor": "劳动"}
        task = context.get("task")
        ct = ct_map.get(task.contract_type if task else "", "未知")
        summary = f"合同类型: {ct}；风险模式: {critical_count} CRITICAL；法条: {len(citations)}条；{len(self.trace)}步推理"

        # 只要风险>0就需要人工复核
        needs_review = risk_score_val > 0 or risk_level_val not in ("LOW",)

        report = ApprovalReport(
            task_id=task.task_id if task else "",
            status="needs_review" if needs_review else "approved",
            risk_score=float(risk_score_val),
            risk_level=str(risk_level_val),
            risk_breakdown=risk.get("breakdown", []) if isinstance(risk, dict) else [],
            risk_advice=str(risk.get("advice", "")) if isinstance(risk, dict) else "",
            mismatch_fields=risk_patterns,
            citations=citations,
            review_summary=summary,
            agent_traces=self.trace,
            total_latency_ms=round(total_ms, 2),
        )
        await self.audit.log_report(report)
        return report
