"""Alembic environment configuration for DarkAtlas.

All active SQLAlchemy models are explicitly imported here before
`target_metadata = Base.metadata` is assigned. This is REQUIRED — without
these imports, Alembic's auto-generation will produce an empty migration
because the ORM mapper won't know about any table definitions.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so `app.*` imports resolve correctly
# whether Alembic is run from the project root or a subdirectory.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# App imports — order matters:
# 1. Import Base first (creates the metadata registry)
# 2. Import all models BEFORE assigning target_metadata so their table
#    definitions are registered on Base.metadata
# ---------------------------------------------------------------------------
from app.database import Base  # noqa: E402
from app.models.asset_model import Asset  # noqa: E402, F401
from app.models.relationship_model import AssetRelationship  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
from app.config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to the .ini file values
# ---------------------------------------------------------------------------
config = context.config

# Override the sqlalchemy.url from the .ini placeholder with the real URL
# sourced from our Pydantic settings (reads from .env automatically)
config.set_main_option("sqlalchemy.url", settings.DB_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the metadata object that Alembic will diff against the database
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live connection).

    Useful for reviewing migration SQL before applying it, or for environments
    where a direct DB connection is not available during the CI pipeline.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (applies changes to a live database connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Compare server-side defaults to detect implicit changes
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
