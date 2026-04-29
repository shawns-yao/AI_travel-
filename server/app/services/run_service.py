"""Run service: orchestrates agent execution with SSE event streaming."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app.core.dag import DAGExecutor, DAGPlan, EventEmitter, build_travel_dag
from app.core.agent import agent_registry
from app.core.logging import get_logger
from app.memory.manager import MemoryManager

logger = get_logger("run_service")

# In-memory store for active runs and their event queues
_active_queues: dict[str, asyncio.Queue] = {}
_active_tasks: dict[str, asyncio.Task] = {}
_run_results: dict[str, dict[str, Any]] = {}


def get_queue(run_id: str) -> asyncio.Queue | None:
    return _active_queues.get(run_id)


async def create_run(query: str, user_id: str = "anonymous") -> dict[str, Any]:
    """Create a new run, start execution in background, return immediately."""
    run_id = str(uuid.uuid4())

    # Create event queue for SSE
    queue: asyncio.Queue = asyncio.Queue()
    _active_queues[run_id] = queue

    # Start execution in background
    task = asyncio.create_task(_execute_run(run_id, query, user_id, queue))
    _active_tasks[run_id] = task

    return {"run_id": run_id, "status": "pending"}


async def _execute_run(
    run_id: str,
    query: str,
    user_id: str,
    queue: asyncio.Queue,
) -> None:
    """Background task: execute the DAG and push events to the queue."""
    try:
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

        # Build context for the first node
        run_context = {
            "query": query,
            "user_id": user_id,
            "run_id": run_id,
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
        output = {}
        for node in result_plan.nodes:
            if node.result and node.result.success:
                output[node.agent_name] = node.result.output

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
            "data": {"result": output},
        })

        await mm.complete_run()

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
