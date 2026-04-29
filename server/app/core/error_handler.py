"""Error handling and fallback strategies for agent execution."""

from __future__ import annotations

import json
import asyncio
from typing import Any, Callable, Awaitable

from app.core.exceptions import AgentRuntimeError
from app.core.logging import get_logger, log_retry, log_fallback


logger = get_logger("error_handler")


class LLMResponseError(AgentRuntimeError):
    """Raised when LLM returns an invalid or unparseable response."""


class AgentTimeoutError(AgentRuntimeError):
    """Raised when an agent exceeds its execution timeout."""


# ── LLM response parsing ───────────────────────────────────

def safe_json_parse(raw: str, fallback: dict | None = None) -> dict:
    """Parse LLM response as JSON with fallback strategies.

    Attempts:
    1. Direct JSON parse
    2. Extract JSON from markdown code blocks
    3. Extract JSON between first { and last }
    """
    if fallback is None:
        fallback = {}

    # Strategy 1: Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from ```json ... ``` block
    if "```json" in raw:
        try:
            start = raw.index("```json") + 7
            end = raw.index("```", start)
            return json.loads(raw[start:end].strip())
        except (ValueError, json.JSONDecodeError):
            pass

    # Strategy 3: Extract between first { and last }
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    logger.warning("json_parse_failed", raw_preview=raw[:200])
    return fallback


def safe_json_parse_list(raw: str) -> list:
    """Parse LLM response as JSON array with fallback."""
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        pass

    # Try extracting array
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    logger.warning("json_array_parse_failed", raw_preview=raw[:200])
    return []


# ── Agent execution with timeout ────────────────────────────

async def execute_with_timeout(
    coro: Awaitable[Any],
    timeout_seconds: float,
    agent_name: str = "unknown",
) -> Any:
    """Execute a coroutine with a timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error("agent_timeout", agent=agent_name, timeout=timeout_seconds)
        raise AgentTimeoutError(f"Agent '{agent_name}' timed out after {timeout_seconds}s")


# ── Retry with backoff ─────────────────────────────────────

async def retry_with_backoff(
    fn: Callable[..., Awaitable[Any]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    agent_name: str = "unknown",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute an async function with exponential backoff retry."""
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await fn(*args, **kwargs)
        except AgentTimeoutError:
            raise  # Don't retry timeouts
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                log_retry(logger, agent_name, attempt + 1, max_retries, delay=delay)
                await asyncio.sleep(delay)

    log_fallback(logger, agent_name, f"All {max_retries} retries failed: {last_error}")
    raise last_error  # type: ignore[misc]
