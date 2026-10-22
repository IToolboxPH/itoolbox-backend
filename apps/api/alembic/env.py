from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from base import Base  # noqa: E402
import models  # noqa: E402 — registers all ORM models with Base.metadata

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# MIGRATION_DATABASE_URL (a direct connection) wins when set; local dev uses DATABASE_URL.
DATABASE_URL = os.getenv(
    "MIGRATION_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://itoolbox:itoolbox@localhost:5435/itoolbox_db"),
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0},
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    except OSError as exc:
        # Build environment has no network — skip here, lifespan handles it.
        print(f"[alembic] Skipping migration (no network): {exc}", flush=True)
    finally:
        await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
