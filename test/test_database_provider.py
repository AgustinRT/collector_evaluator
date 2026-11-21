import logging
from unittest.mock import MagicMock

import psycopg
import pytest
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from src.infraestructure.persistence import database_provider
from src.infraestructure.persistence.database_provider import (
    DatabaseSettings,
    OutdatedSchemaError,
    create_schema,
    provide_engine,
    resolve_postgres_url,
)
from src.infraestructure.persistence.entities.base import Base
from src.infraestructure.persistence.in_memory.database import enable_foreign_keys

POSTGRES_URL = "postgresql://user:pw@db:5432/app"


def _settings(**kwargs) -> DatabaseSettings:
    return DatabaseSettings(_env_file=None, **kwargs)


def _connection_error() -> OperationalError:
    return OperationalError("connect", {}, psycopg.OperationalError("connection refused"))


@pytest.fixture
def postgres_engine(monkeypatch):
    """
    Replaces the PostgreSQL engine by a mock and records the URL and timeout it was created with.
    """
    engine = MagicMock(name="postgres_engine")
    engine.calls = []

    def fake_create_postgres_engine(url, connect_timeout):
        engine.calls.append((url, connect_timeout))
        return engine

    monkeypatch.setattr(database_provider, "create_postgres_engine", fake_create_postgres_engine)
    return engine


@pytest.fixture
def unconfigured_postgres(monkeypatch):
    # Neither DATABASE_URL nor a usable .env.persistence: POSTGRES_* settings are incomplete.
    monkeypatch.setitem(database_provider.PostgresSettings.model_config, "env_file", None)


def _assert_in_memory(engine):
    assert (engine.url.drivername, engine.url.database) == ("sqlite+pysqlite", ":memory:")
    assert isinstance(engine.pool, StaticPool)
    # SQLite only enforces foreign keys (item -> owner) when enabled on each connection.
    assert event.contains(engine, "connect", enable_foreign_keys)


def test_enable_foreign_keys_turns_the_sqlite_pragma_on():
    dbapi_connection = MagicMock()

    enable_foreign_keys(dbapi_connection, None)

    dbapi_connection.cursor.return_value.execute.assert_called_once_with("PRAGMA foreign_keys=ON")


# --- resolve_postgres_url -------------------------------------------------------------------------

def test_explicit_url_takes_precedence_over_postgres_settings(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "ignored")

    url = resolve_postgres_url(_settings(url=POSTGRES_URL))

    assert (url.drivername, url.host, url.database) == ("postgresql+psycopg", "db", "app")


def test_url_is_built_from_postgres_settings_when_not_given(monkeypatch):
    for name, value in {"HOST": "pg", "DB": "collector", "USER": "u", "PASSWORD": "p"}.items():
        monkeypatch.setenv(f"POSTGRES_{name}", value)

    url = resolve_postgres_url(_settings())

    assert (url.host, url.database, url.username) == ("pg", "collector", "u")


def test_database_name_overrides_the_one_in_the_url():
    url = resolve_postgres_url(_settings(url=POSTGRES_URL, name="other_db"))

    assert (url.host, url.database) == ("db", "other_db")


def test_settings_are_read_from_database_environment_variables(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    monkeypatch.setenv("DATABASE_NAME", "from_env")
    monkeypatch.setenv("DATABASE_FALLBACK_TO_MEMORY", "false")
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT", "9")

    settings = _settings()

    assert settings.url.get_secret_value() == POSTGRES_URL
    assert (settings.name, settings.fallback_to_memory, settings.connect_timeout) == ("from_env", False, 9)
    assert "pw" not in repr(settings)


# --- provide_engine -------------------------------------------------------------------------------

def test_returns_postgres_engine_when_reachable(postgres_engine):
    engine = provide_engine(_settings(url=POSTGRES_URL, connect_timeout=2))

    assert engine is postgres_engine
    ((url, timeout),) = postgres_engine.calls
    assert (url.host, url.database, timeout) == ("db", "app", 2)
    postgres_engine.connect.assert_called_once()
    postgres_engine.dispose.assert_not_called()


def test_falls_back_to_in_memory_engine_when_postgres_is_unreachable(postgres_engine, caplog):
    postgres_engine.connect.side_effect = _connection_error()

    with caplog.at_level(logging.WARNING):
        engine = provide_engine(_settings(url=POSTGRES_URL))

    _assert_in_memory(engine)
    postgres_engine.dispose.assert_called_once()
    assert "PostgreSQL is unavailable (connection refused)" in caplog.text
    assert "in-memory" in caplog.text


def test_unreachable_postgres_fails_when_fallback_is_disabled(postgres_engine):
    postgres_engine.connect.side_effect = _connection_error()

    with pytest.raises(OperationalError):
        provide_engine(_settings(url=POSTGRES_URL, fallback_to_memory=False))

    postgres_engine.dispose.assert_called_once()


def test_falls_back_to_in_memory_engine_when_postgres_is_not_configured(unconfigured_postgres, postgres_engine):
    engine = provide_engine(_settings())

    _assert_in_memory(engine)
    assert postgres_engine.calls == []


def test_missing_configuration_fails_when_fallback_is_disabled(unconfigured_postgres, postgres_engine):
    with pytest.raises(ValidationError):
        provide_engine(_settings(fallback_to_memory=False))


def test_non_postgres_url_is_a_configuration_error_even_with_fallback():
    with pytest.raises(ValueError, match="Expected a PostgreSQL URL"):
        provide_engine(_settings(url="mysql://user@db/app"))


# --- create_schema --------------------------------------------------------------------------------

def _existing_columns(monkeypatch, **overrides: list[str]) -> None:
    """
    Makes the (mocked) database report the columns of each table: complete, unless overridden.
    """
    complete = {name: [column.name for column in table.columns] for name, table in Base.metadata.tables.items()}
    columns = complete | overrides
    inspector = MagicMock()
    inspector.get_columns.side_effect = lambda table: [{"name": name} for name in columns[table]]
    monkeypatch.setattr(database_provider, "inspect", lambda engine: inspector)


@pytest.fixture
def create_all(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(Base.metadata, "create_all", mock)
    return mock


def _engine(dialect: str) -> MagicMock:
    engine = MagicMock(name=f"{dialect}_engine")
    engine.dialect.name = dialect
    return engine


def test_create_schema_on_postgres_applies_the_sql_script(monkeypatch, create_all):
    _existing_columns(monkeypatch)
    apply_schema = MagicMock()
    monkeypatch.setattr(database_provider, "apply_schema", apply_schema)
    engine = _engine("postgresql")

    create_schema(engine)

    # The script also creates the history tables and triggers, which the entities do not describe.
    apply_schema.assert_called_once_with(engine)
    create_all.assert_not_called()


def test_create_schema_elsewhere_creates_the_entities(monkeypatch, create_all):
    _existing_columns(monkeypatch)
    apply_schema = MagicMock()
    monkeypatch.setattr(database_provider, "apply_schema", apply_schema)
    engine = _engine("sqlite")

    create_schema(engine)

    create_all.assert_called_once_with(engine)
    apply_schema.assert_not_called()
    assert {"user", "item_collection", "collection", "collection_item"} <= set(Base.metadata.tables)


def test_create_schema_rejects_a_table_created_by_an_older_version(monkeypatch, create_all):
    # The user table as created before email and location existed.
    _existing_columns(monkeypatch, user=["id", "username", "status", "evaluation"])

    with pytest.raises(OutdatedSchemaError) as exc_info:
        create_schema(_engine("sqlite"))

    assert "table 'user' is missing columns ['email', 'latitude', 'longitude']" in str(exc_info.value)
