from logging.config import fileConfig
import asyncio
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from cr_portal.core.config import settings
from cr_portal.db.base import Base
import cr_portal.models  # noqa: F401
config=context.config; config.set_main_option('sqlalchemy.url',settings.DATABASE_URL)
if config.config_file_name is not None: fileConfig(config.config_file_name)
target_metadata=Base.metadata
def offline():
    context.configure(url=config.get_main_option('sqlalchemy.url'),target_metadata=target_metadata,literal_binds=True,dialect_opts={'paramstyle':'named'})
    with context.begin_transaction(): context.run_migrations()
def sync_run(c):
    context.configure(connection=c,target_metadata=target_metadata)
    with context.begin_transaction(): context.run_migrations()
async def online():
    e=async_engine_from_config(config.get_section(config.config_ini_section,{}),prefix='sqlalchemy.',poolclass=pool.NullPool)
    async with e.connect() as c: await c.run_sync(sync_run)
    await e.dispose()
if context.is_offline_mode(): offline()
else: asyncio.run(online())
