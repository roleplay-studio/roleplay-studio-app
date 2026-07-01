"""Alembic migration environment (async).

Uses SQLModel.metadata for autogenerate. DB URL is taken from the project's
Settings so it stays in sync with the application (env vars override .env).
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import SQLModel + every model so its metadata is fully populated for autogenerate.
from sqlmodel import SQLModel

from alembic import context
from app.infrastructure.config import Settings
from app.infrastructure.db import models  # noqa: F401  (side-effect import)

config = context.config

# Override the URL from alembic.ini with the project's real settings.
# This keeps the DB path in one place (env var / Settings / .env) and lets
# Alembic follow the same path the app uses.
config.set_main_option(
    "sqlalchemy.url",
    Settings.from_env().db_url_for_alembic,
)

# Logging — only if a config file was provided.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite supports ALTER via batch mode
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
