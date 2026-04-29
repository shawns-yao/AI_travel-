"""Run memory: tracks agent execution traces, tool results, and failures."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from app.core.logging import get_logger
from app.db.models import AgentRun
from app.db.session import async_session_factory

logger = get_logger("run_memory")


class RunMemory:
    """Records and retrieves agent execution trace data.

    Tracks:
      - DAG plan structure
      - Agent execution status and results
      - Tool call inputs/outputs
      - Error details and failure reasons
      - Token usage
    """

    def __init__(self, run_id: uuid.UUID | None = None) -> None:
        self.run_id = run_id

    async def create_run(self, user_id: uuid.UUID, query: str, run_id: uuid.UUID | None = None) -> uuid.UUID:
        rid = run_id or uuid.uuid4()
        async with async_session_factory() as session:
            run = AgentRun(
                id=rid,
                user_id=user_id,
                query=query,
                status="pending",
                events=[],
            )
            session.add(run)
            await session.commit()
        self.run_id = rid
        return rid

    async def start_run(self) -> None:
        await self._update(status="running", started_at=datetime.now(timezone.utc))

    async def complete_run(self, plan_id: uuid.UUID | None = None) -> None:
        await self._update(
            status="completed",
            plan_id=plan_id,
            completed_at=datetime.now(timezone.utc),
        )

    async def fail_run(self, error_msg: str) -> None:
        await self._update(
            status="failed",
            error_msg=error_msg,
            completed_at=datetime.now(timezone.utc),
        )

    async def log_event(self, event: dict[str, Any]) -> None:
        """Append an event to the run's event log."""
        async with async_session_factory() as session:
            run = await session.get(AgentRun, self.run_id)
            if run:
                events = list(run.events) if run.events else []
                events.append(event)
                run.events = events
                await session.commit()

    async def set_dag_plan(self, dag_plan: dict[str, Any]) -> None:
        await self._update(dag_plan=dag_plan)

    async def get_events(self) -> list[dict[str, Any]]:
        async with async_session_factory() as session:
            run = await session.get(AgentRun, self.run_id)
            return list(run.events) if run and run.events else []

    async def get_status(self) -> dict[str, Any]:
        async with async_session_factory() as session:
            run = await session.get(AgentRun, self.run_id)
            if not run:
                return {}
            return {
                "run_id": str(run.id),
                "status": run.status,
                "query": run.query,
                "error_msg": run.error_msg,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "events_count": len(run.events) if run.events else 0,
            }

    async def get_failures(self) -> list[dict[str, Any]]:
        """Extract failure information from event log."""
        events = await self.get_events()
        return [
            e for e in events
            if e.get("type") in ("agent.completed", "tool.completed")
            and not e.get("data", {}).get("success", True)
        ]

    async def _update(self, **kwargs: Any) -> None:
        async with async_session_factory() as session:
            stmt = update(AgentRun).where(AgentRun.id == self.run_id).values(**kwargs)
            await session.execute(stmt)
            await session.commit()
