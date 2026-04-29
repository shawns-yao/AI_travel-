"""Information cache for external API results.

Uses Redis as the fast cache and PostgreSQL as a persistent fallback.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.models import ExternalAPICache
from app.db.redis import get_redis
from app.db.session import async_session_factory

logger = get_logger("information_cache")


class InformationCache:
    """Cache normalized external information by namespace + key."""

    def __init__(self, namespace: str, ttl_seconds: int = 3600) -> None:
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds

    def _cache_key(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"info:{self.namespace}:{digest}"

    async def get(self, key: str) -> Any | None:
        cache_key = self._cache_key(key)
        redis = await get_redis()
        if redis is not None:
            raw = await redis.get(cache_key)
            if raw:
                logger.info("information_cache.redis_hit", namespace=self.namespace)
                return json.loads(raw)

        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            stmt = select(ExternalAPICache).where(
                ExternalAPICache.cache_key == cache_key,
                ExternalAPICache.expires_at > now,
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            logger.info("information_cache.db_hit", namespace=self.namespace)
            if redis is not None:
                await redis.set(cache_key, json.dumps(row.payload, default=str), ex=self.ttl_seconds)
            return row.payload

    async def set(self, key: str, payload: Any) -> None:
        cache_key = self._cache_key(key)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)

        redis = await get_redis()
        if redis is not None:
            await redis.set(cache_key, json.dumps(payload, default=str), ex=self.ttl_seconds)

        async with async_session_factory() as session:
            row = await session.get(ExternalAPICache, cache_key)
            if row is None:
                row = ExternalAPICache(
                    cache_key=cache_key,
                    namespace=self.namespace,
                    payload=payload,
                    expires_at=expires_at,
                )
                session.add(row)
            else:
                row.payload = payload
                row.expires_at = expires_at
            await session.commit()
