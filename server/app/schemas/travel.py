from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ActivitySchema(BaseModel):
    id: str
    name: str
    type: str
    description: str
    location: str
    duration: str
    time: str
    cost: float = 0.0
    source: str | None = None


class MealSchema(BaseModel):
    id: str
    name: str
    type: str
    cuisine: str
    location: str
    time: str
    cost: float = 0.0


class DailyPlanSchema(BaseModel):
    day: int
    date: str
    activities: list[ActivitySchema] = []
    meals: list[MealSchema] = []
    notes: str = ""


class WeatherDay(BaseModel):
    date: str
    condition: str
    temp_high: float
    temp_low: float
    humidity: float
    recommendation: str


class WeatherResultSchema(BaseModel):
    forecast: list[WeatherDay]
    risk_analysis: str = ""


class BudgetBreakdownSchema(BaseModel):
    total_budget: float
    allocated: dict[str, float]
    spent: float
    warnings: list[str] = []


class CriticIssueSchema(BaseModel):
    severity: str
    category: str
    description: str
    suggestion: str


class CriticReportSchema(BaseModel):
    score: float
    issues: list[CriticIssueSchema] = []
    suggestions: list[str] = []
    needs_replan: bool = False


class MemoryItemSchema(BaseModel):
    memory_type: str
    content: str
    confidence: float
    source: str


class MemoryContextSchema(BaseModel):
    short_term: list[MemoryItemSchema] = []
    long_term: list[MemoryItemSchema] = []


class TravelPlanResponse(BaseModel):
    id: UUID
    destination: str
    duration: int
    start_date: str | None = None
    budget: float | None = None
    preferences: list[str] = []
    daily_plans: list[DailyPlanSchema] = []
    weather: WeatherResultSchema | None = None
    budget_breakdown: BudgetBreakdownSchema | None = None
    critic_report: CriticReportSchema | None = None
    memory_context: MemoryContextSchema | None = None
    status: str
    version: int
    created_at: datetime


class FeedbackRequest(BaseModel):
    plan_id: UUID
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = None
