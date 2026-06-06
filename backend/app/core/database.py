from collections.abc import AsyncGenerator

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database_url import normalize_async_database_url
from app.models import Role
from app.models.base import Base

settings = get_settings()
database_url, connect_args = normalize_async_database_url(settings.database_url)


def is_serverless_runtime() -> bool:
    return os.getenv("VERCEL") == "1" or os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None


def should_run_startup_db_init() -> bool:
    if os.getenv("SKIP_STARTUP_DB_INIT", "").lower() in ("1", "true", "yes"):
        return False
    return not is_serverless_runtime()


# Vercel/serverless: no persistent pool. Local/dev: SQLAlchemy default async pool.
_use_null_pool = is_serverless_runtime() or "neon.tech" in database_url
_engine_kwargs: dict = {"echo": settings.debug}
if connect_args:
    _engine_kwargs["connect_args"] = connect_args
if _use_null_pool:
    _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(database_url, **_engine_kwargs)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def ensure_default_roles(session: AsyncSession) -> None:
    result = await session.execute(select(Role).limit(1))
    if result.scalar_one_or_none() is not None:
        return

    session.add_all(
        [
            Role(name="owner", description="Business owner"),
            Role(name="manager", description="Manager"),
            Role(name="employee", description="Employee"),
        ]
    )
    await session.flush()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await ensure_default_roles(session)
        await session.commit()
