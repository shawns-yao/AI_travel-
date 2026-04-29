"""MemoryManager: orchestrates ShortTerm, LongTerm, and Run memory layers."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.logging import get_logger
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemoryStore
from app.memory.run_memory import RunMemory

logger = get_logger("memory_manager")


class MemoryManager:
    """Unified interface for all three memory layers.

    Usage:
        mm = MemoryManager(run_id="run-123", user_id=user_uuid)
        await mm.init_run(query="...")
        await mm.remember("用户喜欢慢节奏旅行", memory_type="preference")
        memories = await mm.search("travel preferences", embedding=[...])
        await mm.complete_run()
    """

    def __init__(self, run_id: uuid.UUID | str, user_id: uuid.UUID | str) -> None:
        self.run_id = uuid.UUID(run_id) if isinstance(run_id, str) else run_id
        self.user_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        self.short_term = ShortTermMemory(str(self.run_id))
        self.long_term = LongTermMemoryStore(self.user_id)
        self.run_memory = RunMemory(self.run_id)

    # ── Run lifecycle ──────────────────────────────────────

    async def init_run(self, query: str) -> uuid.UUID:
        rid = await self.run_memory.create_run(self.user_id, query, self.run_id)
        await self.short_term.set_context({"query": query, "user_id": str(self.user_id)})
        await self.run_memory.start_run()
        return rid

    async def complete_run(self, plan_id: uuid.UUID | None = None) -> None:
        await self.run_memory.complete_run(plan_id)

    async def fail_run(self, error_msg: str) -> None:
        await self.run_memory.fail_run(error_msg)

    # ── Short-term operations ──────────────────────────────

    async def add_message(self, role: str, content: str) -> None:
        await self.short_term.add_message(role, content)

    async def get_conversation(self) -> dict[str, Any]:
        return await self.short_term.get_all()

    async def set_context(self, key: str, value: Any) -> None:
        await self.short_term.update_context({key: value})

    async def get_context(self) -> dict[str, Any]:
        return await self.short_term.get_context()

    # ── Long-term operations ───────────────────────────────

    async def remember(
        self,
        content: str,
        memory_type: str = "preference",
        embedding: list[float] | None = None,
        source: str = "system",
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> uuid.UUID:
        return await self.long_term.store(
            content=content,
            memory_type=memory_type,
            embedding=embedding,
            source=source,
            confidence=confidence,
            metadata=metadata,
        )

    async def search_memories(
        self,
        query_embedding: list[float],
        memory_type: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        return await self.long_term.search(
            query_embedding=query_embedding,
            memory_type=memory_type,
            top_k=top_k,
        )

    async def get_recent_memories(
        self,
        limit: int = 10,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self.long_term.get_recent(limit=limit, memory_type=memory_type)

    # ── Run trace operations ───────────────────────────────

    async def log_event(self, event: dict[str, Any]) -> None:
        await self.run_memory.log_event(event)

    async def get_events(self) -> list[dict[str, Any]]:
        return await self.run_memory.get_events()

    async def get_failures(self) -> list[dict[str, Any]]:
        return await self.run_memory.get_failures()

    async def get_status(self) -> dict[str, Any]:
        return await self.run_memory.get_status()

    async def set_dag_plan(self, dag_plan: dict[str, Any]) -> None:
        await self.run_memory.set_dag_plan(dag_plan)

    # ── Cleanup ────────────────────────────────────────────

    async def clear_short_term(self) -> None:
        await self.short_term.clear()
