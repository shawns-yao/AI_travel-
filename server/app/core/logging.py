"""Structured logging with structlog for agent observability."""

from __future__ import annotations

import json
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import structlog
from structlog.types import Processor

# ── Shared context ─────────────────────────────────────────

shared_processors: list[Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.dev.ConsoleRenderer()
    if sys.stderr.isatty()
    else structlog.processors.JSONRenderer(),
]

structlog.configure(
    processors=shared_processors,
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: str = "agent") -> structlog.BoundLogger:
    return structlog.get_logger(name)


# ── Timing utilities ───────────────────────────────────────

@asynccontextmanager
async def log_duration(
    logger: structlog.BoundLogger,
    event: str,
    **context: Any,
) -> AsyncIterator[None]:
    """Log the duration of an async operation."""
    start = time.monotonic()
    try:
        yield
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(f"{event}.completed", duration_ms=round(duration_ms, 2), **context)
    except Exception:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error(f"{event}.failed", duration_ms=round(duration_ms, 2), **context)
        raise


# ── Structured trace helpers ────────────────────────────────

def log_agent_start(logger: structlog.BoundLogger, agent_name: str, run_id: str, **ctx: Any) -> None:
    logger.info("agent.started", agent=agent_name, run_id=run_id, **ctx)


def log_agent_done(logger: structlog.BoundLogger, agent_name: str, run_id: str, duration_ms: float, **ctx: Any) -> None:
    logger.info("agent.completed", agent=agent_name, run_id=run_id, duration_ms=round(duration_ms, 2), **ctx)


def log_tool_call(logger: structlog.BoundLogger, tool_name: str, run_id: str, args: dict, **ctx: Any) -> None:
    logger.info("tool.called", tool=tool_name, run_id=run_id, args=json.dumps(args, default=str), **ctx)


def log_tool_result(logger: structlog.BoundLogger, tool_name: str, run_id: str, success: bool, duration_ms: float, **ctx: Any) -> None:
    logger.info("tool.completed", tool=tool_name, run_id=run_id, success=success, duration_ms=round(duration_ms, 2), **ctx)


def log_memory_hit(logger: structlog.BoundLogger, memory_type: str, count: int, run_id: str, **ctx: Any) -> None:
    logger.info("memory.hit", memory_type=memory_type, count=count, run_id=run_id, **ctx)


def log_memory_write(logger: structlog.BoundLogger, memory_type: str, run_id: str, **ctx: Any) -> None:
    logger.info("memory.write", memory_type=memory_type, run_id=run_id, **ctx)


def log_error(logger: structlog.BoundLogger, error: Exception, agent_name: str = "", run_id: str = "", **ctx: Any) -> None:
    logger.error(
        "agent.error",
        agent=agent_name,
        run_id=run_id,
        error_type=type(error).__name__,
        error_msg=str(error),
        **ctx,
    )


def log_retry(logger: structlog.BoundLogger, agent_name: str, attempt: int, max_retries: int, **ctx: Any) -> None:
    logger.warning("agent.retry", agent=agent_name, attempt=attempt, max_retries=max_retries, **ctx)


def log_fallback(logger: structlog.BoundLogger, agent_name: str, reason: str, **ctx: Any) -> None:
    logger.warning("agent.fallback", agent=agent_name, reason=reason, **ctx)
