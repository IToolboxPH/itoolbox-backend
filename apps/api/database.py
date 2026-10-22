from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings

settings = get_settings()

# statement_cache_size=0 keeps the engine usable behind a transaction-mode
# pooler (Supabase's Supavisor) if this ever moves off local Postgres.
engine = create_async_engine(
    settings.database_url,
    connect_args={"statement_cache_size": 0},
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
