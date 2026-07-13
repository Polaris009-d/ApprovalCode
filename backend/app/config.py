"""
ApprovalCode Configuration
参照 Claude Code 的 settings.json + 环境变量模式
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """全局配置，支持 .env 文件和环境变量"""

    # ---- 应用 ----
    APP_NAME: str = "ApprovalCode"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

    # ---- Redis (短期记忆) ----
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    SESSION_TTL: int = 86400  # 24小时

    # ---- PostgreSQL (长期记忆) ----
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_NAME: str = "approval_code"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    # ---- LLM (DeepSeek) ----
    LLM_MODEL: str = "deepseek-chat"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_TEMPERATURE: float = 0.1

    # ---- Baidu OCR ----
    BAIDU_OCR_API_KEY: str = ""
    BAIDU_OCR_SECRET_KEY: str = ""

    # ---- Agent ----
    MAX_RETRIES: int = 3                    # 工具调用最大重试次数
    MAX_REACT_STEPS: int = 15               # ReAct 循环最大步数
    SUBAGENT_TIMEOUT: int = 60              # 子 Agent 超时（秒）

    # ---- 审批 ----
    APPROVAL_TIMEOUT: int = 300             # 人工审批超时（秒）
    HIGH_RISK_THRESHOLD: float = 80.0       # 高风险阈值

    # ---- 安全 ----
    PROMPT_INJECTION_RULES: str = "security_rules.yaml"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 单例
settings = Settings()
