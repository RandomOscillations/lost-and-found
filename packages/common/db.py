from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

_settings = get_settings()

async_engine: AsyncEngine = create_async_engine(str(_settings.database_url), future=True, echo=_settings.debug)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def lifespan_session() -> AsyncSession:
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db_session() -> AsyncSession:
    async with lifespan_session() as session:
        yield session
