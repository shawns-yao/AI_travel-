"""Run service: orchestrates agent execution with SSE event streaming."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.dag import DAGExecutor, DAGPlan, EventEmitter, build_travel_dag
from app.core.agent import agent_registry
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import TravelPlan
from app.db.session import async_session_factory
from app.memory.manager import MemoryManager
from app.services.plan_normalizer import normalize_daily_plans as _normalize_daily_plans

logger = get_logger("run_service")

DEMO_USER_ID = "00000000-0000-4000-8000-000000000001"

# In-memory store for active runs and their event queues
_active_queues: dict[str, asyncio.Queue] = {}
_active_tasks: dict[str, asyncio.Task] = {}
_run_results: dict[str, dict[str, Any]] = {}


def get_queue(run_id: str) -> asyncio.Queue | None:
    return _active_queues.get(run_id)


async def create_run(query: str, user_id: str = DEMO_USER_ID, api_settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a new run, start execution in background, return immediately."""
    run_id = str(uuid.uuid4())

    # Create event queue for SSE
    queue: asyncio.Queue = asyncio.Queue()
    _active_queues[run_id] = queue

    # Start execution in background
    task = asyncio.create_task(_execute_run(run_id, query, user_id, queue, api_settings or {}))
    _active_tasks[run_id] = task

    return {"run_id": run_id, "status": "pending"}


async def _execute_run(
    run_id: str,
    query: str,
    user_id: str,
    queue: asyncio.Queue,
    api_settings: dict[str, Any],
) -> None:
    """Background task: execute the DAG and push events to the queue."""
    try:
        _apply_runtime_api_settings(api_settings)

        # Initialize memory
        mm = MemoryManager(run_id=run_id, user_id=user_id)
        await mm.init_run(query)

        # Build DAG plan
        plan = build_travel_dag(run_id)
        await mm.set_dag_plan({
            "nodes": [{"agent_name": n.agent_name, "dependencies": n.dependencies} for n in plan.nodes],
        })

        # Create emitter that bridges to SSE queue
        emitter = EventEmitter()
        emitter.subscribe(lambda event: _push_event(queue, event))

        # Create executor
        executor = DAGExecutor(
            registry=agent_registry,
            emitter=emitter,
            agent_timeout=120,
            max_retries=2,
        )

        def emit_progress(event_type: str, **data: Any) -> None:
            emitter.emit(event_type, run_id, **data)

        # Build context for the first node
        run_context = {
            "query": query,
            "user_id": user_id,
            "run_id": run_id,
            "api_settings": _redact_api_settings(api_settings),
            "emit_event": emit_progress,
        }

        # Inject context into IntentAgent (root node)
        intent = plan.get_node("IntentAgent")
        if intent:
            intent.context_override = run_context

        for node in plan.nodes:
            if not node.context_override:
                node.context_override = run_context

        # Execute
        result_plan = await executor.execute(plan)

        # Build final result
        agent_outputs = {}
        for node in result_plan.nodes:
            if node.result and node.result.success:
                agent_outputs[node.agent_name] = node.result.output

        output = _assemble_travel_plan(agent_outputs)
        plan_id = await _persist_travel_plan(output, user_id)
        output["id"] = str(plan_id) if plan_id else run_id
        output["source_run_id"] = run_id
        output["created_at"] = datetime.now(timezone.utc).isoformat()
        await _remember_trip_preferences(mm, output, query)

        _run_results[run_id] = {
            "run_id": run_id,
            "status": "completed",
            "output": output,
            "events": [e.__dict__ for e in emitter.events],
        }

        # Push final result event
        await queue.put({
            "type": "run.completed",
            "run_id": run_id,
            "timestamp": asyncio.get_event_loop().time(),
            "data": {"result": output, "plan_id": str(plan_id) if plan_id else None},
        })

        await mm.complete_run(plan_id=plan_id)

    except Exception as e:
        logger.error("run.execute_failed", run_id=run_id, error=str(e))
        await queue.put({
            "type": "run.failed",
            "run_id": run_id,
            "timestamp": asyncio.get_event_loop().time(),
            "data": {"error": str(e)},
        })
        _run_results[run_id] = {"run_id": run_id, "status": "failed", "error": str(e)}

        try:
            mm = MemoryManager(run_id=run_id, user_id=user_id)
            await mm.fail_run(str(e))
        except Exception:
            pass

    finally:
        # Signal end of stream
        await queue.put(None)
        # Clean up after a delay
        await asyncio.sleep(60)
        _active_queues.pop(run_id, None)
        _active_tasks.pop(run_id, None)


def _push_event(queue: asyncio.Queue, event) -> None:
    """Push an SSEEvent to the asyncio queue."""
    try:
        queue.put_nowait({
            "type": event.type,
            "run_id": event.run_id,
            "timestamp": event.timestamp,
            "data": event.data,
        })
    except asyncio.QueueFull:
        logger.warning("event_queue_full", run_id=event.run_id)


def _clean_text(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip() if ch.isprintable())


def _http_url(value: str, fallback: str) -> str:
    raw = _clean_text(value or fallback).rstrip("/")
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://{raw}"


def _apply_runtime_api_settings(api_settings: dict[str, Any]) -> None:
    if not api_settings:
        return

    llm_key = _clean_text(api_settings.get("llm_api_key"))
    llm_provider = _clean_text(api_settings.get("llm_provider"))
    llm_base_url = _clean_text(api_settings.get("llm_base_url"))
    llm_model = _clean_text(api_settings.get("llm_model"))
    qweather_key = _clean_text(api_settings.get("qweather_api_key"))
    qweather_host = _clean_text(api_settings.get("qweather_host"))
    amap_service_key = _clean_text(api_settings.get("amap_service_key") or api_settings.get("amap_api_key"))
    web_search_provider = _clean_text(api_settings.get("web_search_provider"))
    web_search_key = _clean_text(api_settings.get("web_search_api_key"))
    web_search_base_url = _clean_text(api_settings.get("web_search_base_url"))

    if llm_provider:
        settings.llm_provider = llm_provider
    if llm_key:
        settings.llm_api_key = llm_key
        settings.dashscope_api_key = llm_key
    if llm_base_url:
        settings.llm_base_url = llm_base_url
    if llm_model:
        settings.chat_model = llm_model

    if qweather_key:
        settings.qweather_api_key = qweather_key
    if qweather_host:
        weather_base = _http_url(qweather_host, "devapi.qweather.com")
        settings.qweather_weather_base_url = weather_base
        settings.qweather_geo_base_url = f"{weather_base}/geo"

    if amap_service_key:
        settings.amap_api_key = amap_service_key
    if web_search_provider:
        settings.web_search_provider = web_search_provider
    if web_search_key:
        settings.web_search_api_key = web_search_key
    if web_search_base_url:
        settings.web_search_base_url = web_search_base_url


def _redact_api_settings(api_settings: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(api_settings)
    for key in ("llm_api_key", "qweather_api_key", "amap_api_key", "amap_service_key", "web_search_api_key"):
        if redacted.get(key):
            redacted[key] = "***"
    return redacted


def _assemble_travel_plan(agent_outputs: dict[str, Any]) -> dict[str, Any]:
    intent = agent_outputs.get("IntentAgent", {}) or {}
    weather = agent_outputs.get("WeatherAgent") or None
    budget = agent_outputs.get("BudgetAgent") or None
    planner = agent_outputs.get("PlannerAgent", {}) or {}
    critic = agent_outputs.get("CriticAgent") or None
    memory = agent_outputs.get("MemoryAgent") or None

    preferences = intent.get("preferences") or []
    if isinstance(preferences, str):
        preferences = [p.strip() for p in preferences.split(",") if p.strip()]

    return {
        "destination": intent.get("destination") or "未知目的地",
        "duration": int(intent.get("duration") or 3),
        "start_date": intent.get("start_date") or "",
        "budget": int(intent.get("budget") or 3000),
        "budget_source": intent.get("budget_source") or (budget.get("budget_source") if isinstance(budget, dict) else "user"),
        "plan_variant": intent.get("plan_variant") or "标准版",
        "variant_profile": intent.get("variant_profile") or {},
        "preferences": preferences,
        "weather": weather,
        "daily_plans": _normalize_daily_plans(planner.get("daily_plans", [])),
        "map_data": planner.get("map_data"),
        "budget_breakdown": budget,
        "critic_report": critic,
        "memory_context": memory,
    }


async def _persist_travel_plan(plan: dict[str, Any], user_id: str) -> uuid.UUID | None:
    try:
        uid = uuid.UUID(user_id)
        plan_id = uuid.uuid4()
        async with async_session_factory() as session:
            row = TravelPlan(
                id=plan_id,
                user_id=uid,
                destination=plan["destination"],
                duration=plan["duration"],
                start_date=plan.get("start_date") or None,
                budget=plan.get("budget"),
                preferences=plan.get("preferences", []),
                daily_plans=plan.get("daily_plans", []),
                map_data=plan.get("map_data"),
                weather_data=plan.get("weather"),
                budget_breakdown=plan.get("budget_breakdown"),
                critic_report=plan.get("critic_report"),
                memory_context=plan.get("memory_context"),
                status="generated",
                version=1,
            )
            session.add(row)
            await session.commit()
        return plan_id
    except Exception as e:
        logger.warning("travel_plan.persist_failed", error=str(e))
        return None


async def _remember_trip_preferences(mm: MemoryManager, plan: dict[str, Any], query: str) -> None:
    preferences = [str(item) for item in plan.get("preferences", []) if str(item).strip()]
    destination = plan.get("destination") or "未知目的地"
    duration = plan.get("duration") or 0
    budget = plan.get("budget") or 0
    if not preferences and not query:
        return

    content = (
        f"用户曾规划 {destination}{duration}日游，预算约{budget}元；"
        f"偏好：{('、'.join(preferences) if preferences else '未明确')}；"
        f"原始需求：{query[:200]}"
    )
    embedding = None
    try:
        from app.core.llm import get_embedding

        embedding = await get_embedding(content[:1000])
    except Exception:
        embedding = None

    try:
        await mm.remember(
            content=content,
            memory_type="preference",
            embedding=embedding,
            source="travel_plan",
            confidence=0.75,
            metadata={"destination": destination, "duration": duration, "budget": budget},
        )
    except Exception as e:
        logger.warning("travel_plan.memory_write_failed", error=str(e))


async def get_run_status(run_id: str) -> dict[str, Any] | None:
    """Get current run status."""
    if run_id in _run_results:
        return _run_results[run_id]
    if run_id in _active_queues:
        return {"run_id": run_id, "status": "running"}
    return None


async def cancel_run(run_id: str) -> bool:
    """Cancel a running run."""
    task = _active_tasks.pop(run_id, None)
    if task and not task.done():
        task.cancel()
        _active_queues.pop(run_id, None)
        return True
    return False
