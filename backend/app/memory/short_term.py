"""
Redis 短期记忆 — 会话状态快照 + 断点续跑
参考 Claude Code 的 session context 管理
"""
from typing import Any, Dict, Optional
import json

from ..config import settings


class ShortTermMemory:
    """
    短期记忆（Redis）。

    参考 Claude Code session context:
    - 每次 ReAct 步骤后保存状态快照
    - 支持中断后恢复（断点续跑）
    - TTL 过期自动清理
    """

    def __init__(self):
        import redis.asyncio as aioredis
        self.redis = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            db=settings.REDIS_DB,
            decode_responses=True,
        )

    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def save_session(self, session_id: str, data: Dict[str, Any]):
        """保存会话快照"""
        key = self._session_key(session_id)
        payload = json.dumps(data, ensure_ascii=False, default=str)
        await self.redis.setex(key, settings.SESSION_TTL, payload)

    async def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """恢复会话快照"""
        key = self._session_key(session_id)
        raw = await self.redis.get(key)
        if raw:
            return json.loads(raw)
        return None

    async def delete_session(self, session_id: str):
        """删除会话"""
        await self.redis.delete(self._session_key(session_id))

    async def save_checkpoint(self, session_id: str, step: int,
                              state: Dict[str, Any]):
        """保存断点"""
        key = f"checkpoint:{session_id}:{step}"
        payload = json.dumps(state, ensure_ascii=False, default=str)
        await self.redis.setex(key, settings.SESSION_TTL, payload)

    async def get_latest_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取最新断点"""
        # 扫描所有 checkpoint keys
        cursor = 0
        latest = None
        while True:
            cursor, keys = await self.redis.scan(
                cursor, match=f"checkpoint:{session_id}:*"
            )
            for key in keys:
                raw = await self.redis.get(key)
                if raw:
                    latest = json.loads(raw)
            if cursor == 0:
                break
        return latest
