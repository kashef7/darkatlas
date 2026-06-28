# ruff: noqa: E402
# =============================================================================
# tests/conftest.py — Shared fixtures and SQLite compatibility layer
# =============================================================================
#
# CRITICAL: The SQLite compilation hooks MUST be registered at the very top of
# this file, BEFORE any app module is imported. The `@compiles` decorators
# patch SQLAlchemy's DDL compiler so that PostgreSQL-specific column types
# (ARRAY, JSONB) are rendered as "JSON" when building the in-memory test schema.
# Without this, Base.metadata.create_all() raises a CompileError on SQLite.
#
# Additionally, sqlite3 adapters/converters are registered so that Python
# list and dict objects are transparently serialized to/from JSON strings
# when written to / read from the JSON columns at the DBAPI level.
# =============================================================================

import json
import sqlite3

from sqlalchemy.ext.compiler import compiles
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY, JSONB
from sqlalchemy.sql.type_api import TypeEngine  # noqa: F401 — imported per safeguard spec


# ---------------------------------------------------------------------------
# Hook 1: DDL compilation — teach SQLite to render ARRAY as JSON column type
# ---------------------------------------------------------------------------
@compiles(ARRAY, "sqlite")
def compile_array(element, compiler, **kw):
    return "JSON"


@compiles(PG_ARRAY, "sqlite")
def compile_pg_array(element, compiler, **kw):
    return "JSON"


# ---------------------------------------------------------------------------
# Hook 2: DDL compilation — teach SQLite to render JSONB as JSON column type
# ---------------------------------------------------------------------------
@compiles(JSONB, "sqlite")
def compile_jsonb(element, compiler, **kw):
    return "JSON"


# ---------------------------------------------------------------------------
# Hook 3: DBAPI adapters — serialize Python list/dict to JSON strings on write.
# Do NOT register a JSON converter on read — SQLAlchemy's JSON/JSONB processors
# handle deserialization and double-parsing causes TypeError on SQLite.
# ---------------------------------------------------------------------------
sqlite3.register_adapter(list, lambda v: json.dumps(v))
sqlite3.register_adapter(dict, lambda v: json.dumps(v))


# ---------------------------------------------------------------------------
# App imports — MUST come after all hooks are registered above
# ---------------------------------------------------------------------------
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON as SAJSON, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User, Role
from app.models.asset_model import Asset
from app.models.relationship_model import AssetRelationship
from app.core.security import get_password_hash, create_access_token


# =============================================================================
# Test database engine — in-memory SQLite with PARSE_DECLTYPES enabled
# =============================================================================
SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _patch_postgres_types_for_sqlite() -> None:
    """Swap PostgreSQL-only column types for JSON before create_all on SQLite."""
    for table in Base.metadata.tables.values():
        for column in table.columns:
            col_type = column.type
            if isinstance(col_type, (JSONB, ARRAY, PG_ARRAY)):
                column.type = SAJSON()


_patch_postgres_types_for_sqlite()
Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_dependency_overrides():
    """Prevent conftest DB overrides from leaking into standalone test modules."""
    yield
    app.dependency_overrides.clear()


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def db_session():
    """Provides a clean SQLAlchemy session for each test function.

    After each test, ALL table rows are deleted to ensure full isolation.
    This approach (rather than transaction rollback) is compatible with service
    functions that call db.commit() internally (e.g. process_bulk_import).
    """
    session = TestingSessionLocal()
    yield session

    # Teardown: wipe all data in reverse dependency order (FKs)
    try:
        session.query(AssetRelationship).delete()
        session.query(Asset).delete()
        session.query(User).delete()
        session.commit()
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with the real database overridden by the test session.

    The dependency override ensures that every request processed during a test
    uses the same isolated in-memory SQLite session.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # Lifecycle managed by db_session fixture

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    # Always clear overrides after the test to prevent cross-test contamination
    app.dependency_overrides.clear()


# =============================================================================
# User & token seed fixtures
# =============================================================================

def _seed_user(db_session, username: str, password: str, role: Role) -> User:
    """Creates a user in the test database if one doesn't already exist."""
    existing = db_session.query(User).filter(User.username == username).first()
    if existing:
        return existing
    user = User(
        username=username,
        hashed_password=get_password_hash(password),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db_session) -> User:
    """Pre-seeded admin user."""
    return _seed_user(db_session, "test_admin", "adminpass123", Role.admin)


@pytest.fixture(scope="function")
def editor_user(db_session) -> User:
    """Pre-seeded editor user."""
    return _seed_user(db_session, "test_editor", "editorpass123", Role.editor)


@pytest.fixture(scope="function")
def viewer_user(db_session) -> User:
    """Pre-seeded viewer user."""
    return _seed_user(db_session, "test_viewer", "viewerpass123", Role.viewer)


@pytest.fixture(scope="function")
def admin_token(admin_user) -> str:
    """JWT access token for the admin user (generated directly — no HTTP roundtrip)."""
    return create_access_token(data={"sub": admin_user.username, "role": admin_user.role.value})


@pytest.fixture(scope="function")
def editor_token(editor_user) -> str:
    """JWT access token for the editor user."""
    return create_access_token(data={"sub": editor_user.username, "role": editor_user.role.value})


@pytest.fixture(scope="function")
def viewer_token(viewer_user) -> str:
    """JWT access token for the viewer user."""
    return create_access_token(data={"sub": viewer_user.username, "role": viewer_user.role.value})


# =============================================================================
# Asset factory helper
# =============================================================================

def make_asset_payload(
    type: str = "domain",
    value: str = "example.com",
    source: str = "test",
    tags: list = None,
    metadata: dict = None,
    status: str = "active",
) -> dict:
    """Returns a dict matching the AssetCreate schema (uses 'metadata' alias)."""
    return {
        "type": type,
        "value": value,
        "source": source,
        "tags": tags or [],
        "metadata": metadata or {},
        "status": status,
    }