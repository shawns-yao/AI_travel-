from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load prompts, import agents/tools (triggers registration), init DB
    from app.core.prompts import prompt_manager
    prompts_dir = Path(__file__).parent / "agents" / "prompts"
    if prompts_dir.exists():
        prompt_manager.load_from_dir(prompts_dir)

    # Import triggers agent and tool registration
    import app.tools  # noqa: F401
    import app.agents  # noqa: F401

    from app.db.session import engine
    from app.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown
    from app.db.redis import close_redis
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="AI Travel Agent Platform",
    description="Multi-Agent Intelligent Travel Decision System",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
from app.api.runs import router as runs_router
app.include_router(runs_router)


@app.get("/api/health")
async def health_check():
    from app.core.agent import agent_registry
    from app.core.tool import tool_registry
    from app.core.prompts import prompt_manager

    return {
        "status": "ok",
        "service": "AI Travel Agent Platform",
        "version": "0.1.0",
        "agents": agent_registry.list_names(),
        "tools": tool_registry.list_names(),
        "prompts": prompt_manager.list_versions(),
    }
