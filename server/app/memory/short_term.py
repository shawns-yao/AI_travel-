"""Short-term memory: Redis-based conversation context with TTL."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger, log_memory_hit
from app.db.redis import get_redis

logger = get_logger("short_term_memory")

SHORT_TERM_PREFIX = "run:"
DEFAULT_TTL = settings.short_term_ttl_seconds  # 3600s = 1 hour


class ShortTermMemory:
    """Manages current conversation context stored in Redis.

    Each run gets a Redis hash:
      run:{run_id}:context  → JSON dict
      run:{run_id}:messages → JSON list of conversation messages
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.context_key = f"{SHORT_TERM_PREFIX}{run_id}:context"
        self.messages_key = f"{SHORT_TERM_PREFIX}{run_id}:messages"

    async def set_context(self, data: dict[str, Any]) -> None:
        r = await get_redis()
        if r is None:
            return
        await r.set(self.context_key, json.dumps(data, default=str), ex=DEFAULT_TTL)

    async def get_context(self) -> dict[str, Any]:
        r = await get_redis()
        if r is None:
            return {}
        raw = await r.get(self.context_key)
        return json.loads(raw) if raw else {}

    async def update_context(self, updates: dict[str, Any]) -> None:
        current = await self.get_context()
        current.update(updates)
        await self.set_context(current)

    async def add_message(self, role: str, content: str) -> None:
        r = await get_redis()
        if r is None:
            return
        msg = json.dumps({"role": role, "content": content})
        await r.rpush(self.messages_key, msg)
        await r.expire(self.messages_key, DEFAULT_TTL)

    async def get_messages(self, limit: int = 20) -> list[dict[str, str]]:
        r = await get_redis()
        if r is None:
            return []
        raw = await r.lrange(self.messages_key, -limit, -1)
        return [json.loads(m) for m in raw] if raw else []

    async def get_all(self) -> dict[str, Any]:
        context = await self.get_context()
        messages = await self.get_messages()
        log_memory_hit(logger, "short_term", len(messages), self.run_id)
        return {
            "context": context,
            "messages": messages,
            "message_count": len(messages),
        }

    async def clear(self) -> None:
        r = await get_redis()
        if r is None:
            return
        await r.delete(self.context_key, self.messages_key)
