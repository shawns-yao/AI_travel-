import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "travel"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plans: Mapped[list["TravelPlan"]] = relationship(back_populates="user")
    runs: Mapped[list["AgentRun"]] = relationship(back_populates="user")
    memories: Mapped[list["LongTermMemory"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class TravelPlan(Base):
    __tablename__ = "travel_plans"
    __table_args__ = {"schema": "travel"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("travel.users.id"), nullable=False)
    destination: Mapped[str] = mapped_column(String(200), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    start_date: Mapped[str] = mapped_column(String(20), nullable=True)
    budget: Mapped[int] = mapped_column(Integer, nullable=True)
    preferences: Mapped[dict] = mapped_column(JSONB, default=list)
    daily_plans: Mapped[dict] = mapped_column(JSONB, default=list)
    weather_data: Mapped[dict] = mapped_column(JSONB, default=None, nullable=True)
    budget_breakdown: Mapped[dict] = mapped_column(JSONB, default=None, nullable=True)
    critic_report: Mapped[dict] = mapped_column(JSONB, default=None, nullable=True)
    memory_context: Mapped[dict] = mapped_column(JSONB, default=None, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="plans")
    runs: Mapped[list["AgentRun"]] = relationship(back_populates="plan")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = {"schema": "travel"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("travel.users.id"), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("travel.travel_plans.id"), nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    dag_plan: Mapped[dict] = mapped_column(JSONB, default=None, nullable=True)
    events: Mapped[list] = mapped_column(JSONB, default=list)
    error_msg: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="runs")
    plan: Mapped["TravelPlan"] = relationship(back_populates="runs")


class LongTermMemory(Base):
    __tablename__ = "long_term_memories"
    __table_args__ = (
        Index("idx_memory_user_type", "user_id", "memory_type"),
        Index(
            "idx_memory_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": "100"},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"schema": "travel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("travel.users.id"), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=True)
    source: Mapped[str] = mapped_column(String(100), default="system")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="memories")


class KnowledgeChunk(Base):
    """RAG knowledge base chunks for travel destinations."""
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index(
            "idx_knowledge_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": "100"},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"schema": "travel"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    destination: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TokenUsage(Base):
    """Track token consumption and cost per agent run."""
    __tablename__ = "token_usage"
    __table_args__ = {"schema": "travel"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("travel.agent_runs.id"), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_cny: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
