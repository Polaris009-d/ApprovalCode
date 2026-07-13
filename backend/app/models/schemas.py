"""
核心数据模型
参照 Claude Code 的 Tool Call / Tool Result 结构化协议
"""
import uuid
import time
from datetime import datetime
from enum import Enum
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════
# Agent 状态
# ═══════════════════════════════════════════

class AgentStatus(str, Enum):
    """Agent 生命周期状态，参考 Claude Code subagent 状态机"""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"     # 等待子 Agent 或人工审批
    DONE = "done"
    ERROR = "error"


class AgentState(BaseModel):
    """单个 Agent 的运行时状态"""
    agent_id: str
    agent_type: str                          # master / extract / comply / risk
    status: AgentStatus = AgentStatus.IDLE
    current_step: int = 0
    thought: Optional[str] = None
    plan: Optional[List[str]] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════
# 工具调用协议
# ═══════════════════════════════════════════

class ToolCall(BaseModel):
    """工具调用请求 — 参考 Claude Code Tool Use 协议"""
    call_id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    agent_id: str                            # 调用方
    step: int = 0                            # ReAct 步骤号
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolResult(BaseModel):
    """工具返回结果"""
    call_id: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════
# ReAct 步骤
# ═══════════════════════════════════════════

class ReActStepType(str, Enum):
    THINK = "think"
    PLAN = "plan"
    ACT = "act"
    OBSERVE = "observe"


class ReActStep(BaseModel):
    """单步 ReAct 记录 — 审计日志的基本单元"""
    step_id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:12]}")
    step_num: int
    agent_id: str
    step_type: ReActStepType
    content: str                            # 思考内容 / 计划 / 观察结果
    tool_call: Optional[ToolCall] = None    # ACT 步骤关联
    tool_result: Optional[ToolResult] = None
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════
# 审批任务
# ═══════════════════════════════════════════

class ApprovalTask(BaseModel):
    """用户提交的审批任务"""
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:16]}")
    session_id: str = Field(default_factory=lambda: f"session_{uuid.uuid4().hex[:12]}")
    contract_type: str                      # 采购 / 服务 / 租赁 ...
    contract_files: List[str] = Field(default_factory=list)  # 文件路径列表
    user_input: Dict[str, Any] = Field(default_factory=dict)  # 用户填写的合同信息
    stream: bool = True                     # SSE 流式输出
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalReport(BaseModel):
    """审批报告"""
    task_id: str
    status: str                             # approved / rejected / needs_review
    risk_score: float = 0.0
    risk_level: str = "LOW"                 # LOW / MEDIUM / HIGH
    mismatch_fields: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    review_summary: str = ""
    risk_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    risk_advice: str = ""
    agent_traces: List[ReActStep] = Field(default_factory=list)
    human_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    token_usage: Dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════
# 权限模型
# ═══════════════════════════════════════════

class PermissionDecision(str, Enum):
    """权限决策 — 参考 Claude Code allow/deny/ask 三级模型"""
    ALLOW = "allow"      # 自动通过
    DENY = "deny"        # 自动拒绝
    ASK = "ask"          # 挂起 → SSE 推送人工


class SecurityRule(BaseModel):
    """安全规则"""
    name: str
    pattern: Optional[str] = None           # 正则匹配
    condition: Optional[str] = None         # Python 表达式
    action: PermissionDecision
    message: str
    timeout: int = 300                      # ASK 时的超时秒数


# ═══════════════════════════════════════════
# Pipeline
# ═══════════════════════════════════════════

class PipelineStage(BaseModel):
    """流水线阶段"""
    name: str
    agent_type: str                         # extract / comply / risk
    tools: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)  # 依赖的阶段名

    class Config:
        extra = "allow"
