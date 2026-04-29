import asyncio

import pytest


def pytest_sessionstart(session):
    async def init_db():
        import app.db.models  # noqa: F401
        from app.db.base import Base
        from app.db.session import engine
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS travel"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)

    try:
        asyncio.run(init_db())
    except Exception:
        # Database may not be available (e.g. local dev without Docker)
        pass


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring external infrastructure (DB, Redis, etc.)"
    )
