from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import desc, select
from sqlalchemy import update

from app.db.models import AgentRun, TravelPlan
from app.db.session import async_session_factory
from app.services.run_service import DEMO_USER_ID

router = APIRouter(prefix="/api/plans", tags=["plans"])


def _plan_payload(row: TravelPlan) -> dict:
    daily_plans = []
    for index, item in enumerate(row.daily_plans or [], start=1):
        if not isinstance(item, dict):
            continue
        day = dict(item)
        day["day"] = int(day.get("day") or index)
        day["date"] = str(day.get("date") or "")
        day["activities"] = day.get("activities") if isinstance(day.get("activities"), list) else []
        meals = day.get("meals") if isinstance(day.get("meals"), list) else []
        dinner = next(
            (
                meal
                for meal in meals
                if isinstance(meal, dict)
                and (meal.get("type") == "dinner" or "晚" in str(meal.get("time", "")))
            ),
            meals[0] if meals and isinstance(meals[0], dict) else None,
        )
        if isinstance(dinner, dict):
            dinner = dict(dinner)
            dinner["type"] = "dinner"
            dinner["time"] = "晚上"
            day["meals"] = [dinner]
        else:
            day["meals"] = []
        day["notes"] = str(day.get("notes") or "")
        daily_plans.append(day)

    return {
        "id": str(row.id),
        "destination": row.destination,
        "duration": row.duration,
        "start_date": row.start_date or "",
        "budget": row.budget or 0,
        "preferences": row.preferences or [],
        "daily_plans": daily_plans,
        "map_data": row.map_data,
        "weather": row.weather_data,
        "budget_breakdown": row.budget_breakdown,
        "critic_report": row.critic_report,
        "memory_context": row.memory_context,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


@router.get("")
async def list_plans() -> dict:
    async with async_session_factory() as session:
        stmt = (
            select(TravelPlan)
            .where(TravelPlan.user_id == uuid.UUID(DEMO_USER_ID))
            .order_by(desc(TravelPlan.created_at))
            .limit(20)
        )
        rows = (await session.execute(stmt)).scalars().all()
    return {"plans": [_plan_payload(row) for row in rows]}


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(plan_id: str) -> Response:
    try:
        parsed_id = uuid.UUID(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid plan_id") from exc

    async with async_session_factory() as session:
        stmt = select(TravelPlan).where(
            TravelPlan.id == parsed_id,
            TravelPlan.user_id == uuid.UUID(DEMO_USER_ID),
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Plan not found")

        await session.execute(
            update(AgentRun)
            .where(AgentRun.plan_id == parsed_id)
            .values(plan_id=None)
        )
        await session.delete(row)
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
