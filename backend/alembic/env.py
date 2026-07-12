from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Do NOT overwrite sqlalchemy.url here: db.py::run_migrations(db_path) sets it
# on the Config object it builds before calling command.upgrade(), and that
# value must survive into this env.py unchanged. For plain CLI usage
# (`alembic upgrade head` / `alembic revision --autogenerate`), alembic.ini's
# own `sqlalchemy.url` default (matching config.settings.auth_db_path) applies.

target_metadata = None  # no ORM models in Foroba — migrations are raw DDL only


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
