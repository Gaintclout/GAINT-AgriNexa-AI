
"""Alembic environment for GAINT AgriNexa AI.

PostgreSQL/PostGIS migrations.
Database URL is supplied through the DATABASE_URL environment variable.
No automatic schema changes are performed.
"""

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database import Base
from app import (
    models,
    scim_job_models,
    scim_result_models,
    field_verification_models,
    agent_audit_models,
)

config = context.config
target_metadata = Base.metadata


def database_url():
    url = os.getenv("DATABASE_URL", "")

    if not url.startswith((
        "postgresql://",
        "postgresql+psycopg://",
    )):
        raise RuntimeError(
            "DATABASE_URL must reference PostgreSQL"
        )

    return url


def offline():
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def online():
    section = config.get_section(
        config.config_ini_section
    ) or {}

    section["sqlalchemy.url"] = database_url()

    engine = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    offline()
else:
    online()
