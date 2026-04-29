"""REST + SSE endpoints for agent runs."""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.schemas.run import CreateRunRequest, RunResponse, RunStatusResponse
from app.services.run_service import create_run, get_run_status, cancel_run, get_queue
from app.core.logging import get_logger

logger = get_logger("api.runs")

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=201)
async def start_run(req: CreateRunRequest):
    """Create and start a new agent run."""
    try:
        result = await create_run(query=req.query)
        return RunResponse(
            run_id=result["run_id"],
            status=result["status"],
            created_at=None,  # Will be set by DB
        )
    except Exception as e:
        logger.error("start_run_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run(run_id: str):
    """Get run status and result."""
    status = await get_run_status(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Run not found")

    output = status.get("output", {})
    completed_agents = list(output.keys()) if output else []

    return RunStatusResponse(
        run_id=run_id,
        status=status.get("status", "unknown"),
        completed_agents=completed_agents,
        events_count=len(status.get("events", [])),
    )


@router.get("/{run_id}/events")
async def stream_events(run_id: str, request: Request):
    """SSE endpoint: stream agent execution events in real-time."""
    queue = get_queue(run_id)
    if queue is None:
        # Check if run completed and return result
        status = await get_run_status(run_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Run not found")

        # Run already finished - return legacy events
        async def replay_events():
            for event in status.get("events", []):
                if await request.is_disconnected():
                    break
                yield {"event": "message", "data": json.dumps(event, default=str)}
        return EventSourceResponse(replay_events())

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield {"event": "ping", "data": "{}"}
                    continue

                if event is None:  # End of stream
                    break

                yield {"event": "message", "data": json.dumps(event, default=str)}
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())


@router.post("/{run_id}/cancel")
async def cancel(run_id: str):
    """Cancel a running run."""
    cancelled = await cancel_run(run_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Run not found or already completed")
    return {"status": "cancelled"}
