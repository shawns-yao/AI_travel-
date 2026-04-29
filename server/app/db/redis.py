"""Redis client wrapper with graceful fallback for development."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("redis")

_redis: aioredis.Redis | None = None
_available: bool = True


async def get_redis() -> aioredis.Redis | None:
    """Get Redis connection, returning None if unavailable."""
    global _redis, _available
    if _redis is not None:
        try:
            await _redis.ping()
            return _redis
        except Exception:
            try:
                await _redis.aclose()
            except Exception:
                pass
            _redis = None
    if not _available:
        return None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis.ping()
        logger.info("redis.connected", url=settings.redis_url)
        return _redis
    except Exception:
        _available = False
        logger.warning("redis.unavailable", url=settings.redis_url)
        return None


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
