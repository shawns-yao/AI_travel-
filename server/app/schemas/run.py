from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="User travel request")


class RunResponse(BaseModel):
    run_id: UUID
    status: str
    created_at: datetime


class RunEvent(BaseModel):
    type: str
    run_id: str
    timestamp: float
    data: dict

    model_config = {"from_attributes": True}


class RunStatusResponse(BaseModel):
    run_id: UUID
    status: str
    current_agent: str | None = None
    completed_agents: list[str] = []
    failed_agents: list[str] = []
    events_count: int = 0
