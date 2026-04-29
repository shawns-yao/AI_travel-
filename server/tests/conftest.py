import pytest


def pytest_sessionstart(session):
    import asyncio

    async def init_db():
        import app.db.models  # noqa: F401
        from app.db.base import Base
        from app.db.session import engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_db())


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring external infrastructure (DB, Redis, etc.)"
    )
