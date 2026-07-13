"""
安全规则引擎 + 权限模型
参考 Claude Code 的三级权限: allow / deny / ask
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from ..models.schemas import PermissionDecision, SecurityRule


@dataclass
class SecurityCheckResult:
    """安全规则检查结果"""
    decision: PermissionDecision
    message: str
    rule_name: Optional[str] = None
    timeout: int = 300


class RuleEngine:
    """
    安全规则引擎。

    参考 Claude Code 的 permission system:
    - ALLOW: 自动放行
    - DENY: 自动拦截（Prompt 注入等）
    - ASK: 挂起等待人工确认（SSE 推送）
    """

    def __init__(self, rules: Optional[List[SecurityRule]] = None):
        self.rules: List[SecurityRule] = rules or self._default_rules()

    @staticmethod
    def _default_rules() -> List[SecurityRule]:
        """内置安全规则"""
        return [
            SecurityRule(
                name="prompt_injection_defense",
                pattern=r"(?i)(忽略|无视|绕过|删除|忘记).*(指令|规则|限制|安全)",
                action=PermissionDecision.DENY,
                message="检测到潜在 Prompt 注入攻击",
            ),
            SecurityRule(
                name="high_amount_approval",
                pattern=None,
                condition="contract_amount > 500000",
                action=PermissionDecision.ASK,
                message="合同金额超过50万，需要人工审批",
                timeout=300,
            ),
            SecurityRule(
                name="sensitive_clause_type",
                pattern=r"竞业限制|排他条款|无限连带责任",
                action=PermissionDecision.ASK,
                message="合同包含敏感条款，需要人工复审",
                timeout=600,
            ),
        ]

    async def check(self, agent_result: Dict[str, Any],
                    context: Dict[str, Any]) -> SecurityCheckResult:
        """
        对子 Agent 结果逐一过规则。

        返回第一个命中的非 ALLOW 结果，或 ALLOW。
        """
        for rule in self.rules:
            # 1. 正则匹配
            if rule.pattern:
                text = str(agent_result)
                if re.search(rule.pattern, text):
                    if rule.action == PermissionDecision.DENY:
                        return SecurityCheckResult(
                            decision=PermissionDecision.DENY,
                            message=rule.message,
                            rule_name=rule.name,
                        )
                    elif rule.action == PermissionDecision.ASK:
                        return SecurityCheckResult(
                            decision=PermissionDecision.ASK,
                            message=rule.message,
                            rule_name=rule.name,
                            timeout=rule.timeout,
                        )

            # 2. 条件表达式
            if rule.condition:
                try:
                    # 安全沙箱 evaluate
                    if self._eval_condition(rule.condition, agent_result, context):
                        return SecurityCheckResult(
                            decision=rule.action,
                            message=rule.message,
                            rule_name=rule.name,
                            timeout=rule.timeout,
                        )
                except Exception:
                    pass

        # 全部通过
        return SecurityCheckResult(
            decision=PermissionDecision.ALLOW,
            message="All security checks passed",
        )

    def _eval_condition(self, condition: str, agent_result: Dict,
                        context: Dict) -> bool:
        """
        安全地 evaluate 条件表达式。
        仅允许访问 agent_result 和 context 中的数值字段。
        """
        # 构建安全命名空间
        safe_vars = {}

        # 从 agent_result 提取数值
        if isinstance(agent_result, dict):
            for k, v in agent_result.items():
                if isinstance(v, (int, float)):
                    safe_vars[k] = v
                elif isinstance(k, str) and "amount" in k:
                    try:
                        safe_vars["contract_amount"] = float(str(v).replace(",", ""))
                    except (ValueError, TypeError):
                        pass

        # 从 context 提取
        task = context.get("task")
        if task and hasattr(task, "user_input"):
            raw = task.user_input.get("amount", 0)
            try:
                safe_vars["contract_amount"] = float(str(raw).replace(",", ""))
            except (ValueError, TypeError):
                pass

        try:
            return bool(eval(condition, {"__builtins__": {}}, safe_vars))
        except Exception:
            return False

    def add_rule(self, rule: SecurityRule):
        """热添加规则 — 无需重启"""
        self.rules.append(rule)

    def remove_rule(self, name: str):
        """热移除规则"""
        self.rules = [r for r in self.rules if r.name != name]
