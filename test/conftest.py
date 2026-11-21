import sqlite3
from unittest.mock import create_autospec

import psycopg
import pytest
from sqlalchemy import create_mock_engine
from sqlalchemy.orm import Session

from src.domain.enum.user_status import UserStatus
from src.domain.model.location import Location
from src.domain.model.user import User


@pytest.fixture(autouse=True)
def block_real_database_connections(monkeypatch):
    """
    Safety net: the database must always be mocked, so any real connection attempt fails loudly.
    This covers PostgreSQL (psycopg) and the in-memory fallback (sqlite3).
    """
    def _refuse(*args, **kwargs):
        raise AssertionError("Tests must not open real database connections; mock the session instead.")

    monkeypatch.setattr(psycopg, "connect", _refuse)
    monkeypatch.setattr(psycopg.Connection, "connect", _refuse)
    monkeypatch.setattr(sqlite3, "connect", _refuse)


@pytest.fixture(autouse=True)
def isolate_database_environment(monkeypatch):
    """
    Makes tests independent of the developer's DATABASE_* / POSTGRES_* environment variables.
    """
    for variable in ("URL", "NAME", "FALLBACK_TO_MEMORY", "CONNECT_TIMEOUT"):
        monkeypatch.delenv(f"DATABASE_{variable}", raising=False)
    for variable in ("HOST", "PORT", "DB", "USER", "PASSWORD"):
        monkeypatch.delenv(f"POSTGRES_{variable}", raising=False)


@pytest.fixture
def schema_ddl():
    """
    Returns a function giving the DDL statements create_schema would run on a dialect, captured
    without connecting to any database. Whitespace is collapsed to make assertions readable.
    """
    from src.infraestructure.persistence.entities import item_collection_entity, user_entity  # noqa: F401
    from src.infraestructure.persistence.entities.base import Base

    def capture(url: str) -> list[str]:
        statements = []
        engine = create_mock_engine(
            url,
            lambda sql, *args, **kwargs: statements.append(" ".join(str(sql.compile(dialect=engine.dialect)).split())),
        )
        Base.metadata.create_all(engine, checkfirst=False)
        return statements

    return capture


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True)


@pytest.fixture
def database_assigns_ids(mock_session):
    """
    Simulates the database sequences on the mocked session: on commit, every entity passed to
    ``session.add`` that has no id yet gets the next id (1, 2, 3...).
    """
    added = []
    next_id = iter(range(1, 1_000_000))
    mock_session.add.side_effect = added.append

    def commit():
        for entity in added:
            if entity.id is None:
                entity.id = next(next_id)

    mock_session.commit.side_effect = commit
    return mock_session


@pytest.fixture
def alice():
    return User(
        username="alice",
        email="alice@example.com",
        location=Location(latitude=40.4168, longitude=-3.7038),
        status=UserStatus.ACTIVE,
        evaluation=4.5,
    )
