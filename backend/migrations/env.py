from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool


# Добавляем src в PYTHONPATH
sys.path.append(
    str(Path(__file__).resolve().parents[1] / "src")
)


from cr_portal.core.config import settings
from cr_portal.db.base import Base
from cr_portal.models import User

config = context.config


# Передаем URL из настроек приложения
config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL,
)


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    """

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations in async mode.
    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(
            do_run_migrations
        )

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()

else:
    asyncio.run(
        run_migrations_online()
    )