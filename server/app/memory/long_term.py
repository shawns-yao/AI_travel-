"""Long-term memory: pgvector-based user preference storage and retrieval."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, text

from app.core.config import settings
from app.core.logging import get_logger, log_memory_hit, log_memory_write
from app.db.models import LongTermMemory, User
from app.db.session import async_session_factory


logger = get_logger("long_term_memory")


class LongTermMemoryStore:
    """Store and retrieve user preferences using pgvector similarity search.

    Memory types:
      - preference: travel style, pace, budget sensitivity
      - restriction: dietary, accessibility, scheduling constraints
      - feedback: user ratings and comments on past plans
      - fact: learned facts (e.g., "travels with kids", "prefers window seat")
    """

    def __init__(self, user_id: uuid.UUID) -> None:
        self.user_id = user_id

    async def store(
        self,
        content: str,
        memory_type: str = "preference",
        embedding: list[float] | None = None,
        source: str = "system",
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> uuid.UUID:
        """Store a new memory with optional embedding vector."""
        memory_id = uuid.uuid4()

        async with async_session_factory() as session:
            user = await session.get(User, self.user_id)
            if user is None:
                user = User(
                    id=self.user_id,
                    email=f"{self.user_id}@demo.local",
                    hashed_password="demo",
                    display_name="Demo User",
                )
                session.add(user)
            memory = LongTermMemory(
                id=memory_id,
                user_id=self.user_id,
                memory_type=memory_type,
                content=content,
                embedding=embedding,
                source=source,
                confidence=confidence,
                metadata_=metadata or {},
            )
            session.add(memory)
            await session.commit()

        log_memory_write(logger, memory_type, run_id=str(self.user_id))
        return memory_id

    async def search(
        self,
        query_embedding: list[float],
        memory_type: str | None = None,
        top_k: int | None = None,
        min_confidence: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar memories using cosine similarity."""
        if top_k is None:
            top_k = settings.long_term_top_k
        if min_confidence is None:
            min_confidence = settings.long_term_min_confidence

        async with async_session_factory() as session:
            conditions = [
                LongTermMemory.user_id == self.user_id,
                LongTermMemory.confidence >= min_confidence,
                LongTermMemory.embedding.isnot(None),
            ]
            if memory_type:
                conditions.append(LongTermMemory.memory_type == memory_type)

            # pgvector cosine similarity: 1 - (embedding <=> query_embedding)
            similarity = 1 - LongTermMemory.embedding.cosine_distance(query_embedding)

            stmt = (
                select(
                    LongTermMemory.content,
                    LongTermMemory.memory_type,
                    LongTermMemory.source,
                    LongTermMemory.confidence,
                    similarity.label("similarity"),
                )
                .where(*conditions)
                .order_by(similarity.desc())
                .limit(top_k)
            )

            result = await session.execute(stmt)
            rows = result.all()

        memories = [
            {
                "content": row.content,
                "memory_type": row.memory_type,
                "source": row.source,
                "confidence": row.confidence,
                "similarity": round(float(row.similarity), 4),
            }
            for row in rows
        ]

        log_memory_hit(logger, memory_type or "all", len(memories), run_id=str(self.user_id))
        return memories

    async def get_recent(
        self,
        limit: int = 10,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get most recent memories without embedding search."""
        async with async_session_factory() as session:
            conditions = [LongTermMemory.user_id == self.user_id]
            if memory_type:
                conditions.append(LongTermMemory.memory_type == memory_type)

            stmt = (
                select(LongTermMemory)
                .where(*conditions)
                .order_by(LongTermMemory.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            {
                "id": str(row.id),
                "content": row.content,
                "memory_type": row.memory_type,
                "source": row.source,
                "confidence": row.confidence,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    async def delete(self, memory_id: uuid.UUID) -> bool:
        async with async_session_factory() as session:
            memory = await session.get(LongTermMemory, memory_id)
            if memory:
                await session.delete(memory)
                await session.commit()
                return True
        return False
