from __future__ import annotations

import logging
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

config = context.config
if config.config_file_name is not None:
    # Migrations run in-process on every real (non-":memory:") db.connect()
    # call, incl. app startup — so alembic.ini's [logger_root] (level=WARN)
    # must not clobber the app's own root logging config for the rest of the
    # process. disable_existing_loggers=False stops fileConfig from disabling
    # already-created module loggers outright (e.g. GlitchTip-relevant ones
    # from observability.py); restoring root's level/handlers afterward stops
    # it from silencing the app's own INFO-level logs app-wide post-migration.
    _root = logging.getLogger()
    _prev_level, _prev_handlers = _root.level, list(_root.handlers)
    fileConfig(config.config_file_name, disable_existing_loggers=False)
    _root.setLevel(_prev_level)
    _root.handlers = _prev_handlers

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
