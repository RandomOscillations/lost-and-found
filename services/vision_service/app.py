from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from packages.common.config import get_settings
from packages.common.db import AsyncSessionLocal, async_engine, get_db_session
from packages.common.models import Base

from .router import router


def create_app(
    *,
    engine: AsyncEngine | None = None,
    session_factory: async_sessionmaker | None = None,
    on_startup_hook: Callable[[FastAPI], Awaitable[None]] | None = None,
) -> FastAPI:
    target_engine = engine or async_engine
    sessionmaker = session_factory or AsyncSessionLocal
    settings = get_settings()

    app = FastAPI(title="Vision Service", version="1.0.0")

    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover
        async with target_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        if on_startup_hook:
            await on_startup_hook(app)

    if session_factory is not None:
        async def _override_get_db_session():
            async with sessionmaker() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db_session] = _override_get_db_session

    app.include_router(router)
    return app


app = create_app()
