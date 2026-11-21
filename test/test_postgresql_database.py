from unittest.mock import MagicMock

import pytest
from sqlalchemy import make_url

from src.infraestructure.persistence.postgresql import database
from src.infraestructure.persistence.postgresql.database import PostgresSettings, to_psycopg_url


@pytest.mark.parametrize("url", [
    "postgresql://user:pw@db:5432/app",
    "postgres://user:pw@db:5432/app",
    "postgresql+psycopg://user:pw@db:5432/app",
])
def test_to_psycopg_url_always_uses_psycopg3(url):
    normalized = to_psycopg_url(url)

    assert normalized.drivername == "postgresql+psycopg"
    assert (normalized.host, normalized.port, normalized.database) == ("db", 5432, "app")
    assert normalized.password == "pw"


@pytest.mark.parametrize("url", ["sqlite:///:memory:", "mysql://user@db/app"])
def test_to_psycopg_url_rejects_other_databases(url):
    with pytest.raises(ValueError, match="Expected a PostgreSQL URL"):
        to_psycopg_url(url)


def test_create_postgres_engine_sets_driver_and_connect_timeout(monkeypatch):
    captured = {}
    monkeypatch.setattr(database, "create_engine", lambda url, **kwargs: captured.update(url=url, **kwargs))

    database.create_postgres_engine("postgresql://user:pw@db/app", connect_timeout=3)

    assert captured["url"].drivername == "postgresql+psycopg"
    assert captured["connect_args"] == {"connect_timeout": 3}
    assert captured["pool_pre_ping"] is True


def test_postgres_settings_build_the_url_from_environment(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_DB", "app")
    monkeypatch.setenv("POSTGRES_USER", "user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss/word")

    url = PostgresSettings(_env_file=None).url

    assert url.render_as_string(hide_password=False) == "postgresql+psycopg://user:p%40ss%2Fword@db:5432/app"
    assert make_url(url.render_as_string(hide_password=False)).password == "p@ss/word"


# --- apply_schema ---------------------------------------------------------------------------------

@pytest.fixture
def pooled_connection():
    """
    A mocked pooled connection whose psycopg connection records its autocommit mode at execute time.
    """
    connection = MagicMock(name="pooled_connection")
    psycopg_connection = connection.driver_connection
    psycopg_connection.autocommit = False
    psycopg_connection.autocommit_during_execute = None

    def execute(sql, *args):
        psycopg_connection.autocommit_during_execute = psycopg_connection.autocommit
        psycopg_connection.executed = (sql, args)

    psycopg_connection.execute.side_effect = execute
    return connection


def test_schema_script_exists():
    assert database.SCHEMA_SCRIPT.is_file()
    assert database.SCHEMA_SCRIPT.parts[-3:] == ("database", "schema", "schema.sql")


def test_apply_schema_runs_the_script_in_autocommit_without_parameters(pooled_connection, tmp_path):
    script = tmp_path / "schema.sql"
    script.write_text("BEGIN; SELECT format('%I', 'x'); COMMIT;", encoding="utf-8")
    engine = MagicMock(name="engine")
    engine.raw_connection.return_value = pooled_connection
    psycopg_connection = pooled_connection.driver_connection

    database.apply_schema(engine, script)

    # The script runs its own transaction; with no parameters, "%I" is not taken as a placeholder.
    assert psycopg_connection.executed == ("BEGIN; SELECT format('%I', 'x'); COMMIT;", ())
    assert psycopg_connection.autocommit_during_execute is True
    # The connection goes back to the pool in its normal (transactional) mode.
    assert psycopg_connection.autocommit is False
    pooled_connection.invalidate.assert_not_called()
    pooled_connection.close.assert_called_once()


def test_apply_schema_discards_the_connection_when_the_script_fails(pooled_connection, tmp_path):
    script = tmp_path / "schema.sql"
    script.write_text("BEGIN; broken; COMMIT;", encoding="utf-8")
    pooled_connection.driver_connection.execute.side_effect = RuntimeError("syntax error")
    engine = MagicMock(name="engine")
    engine.raw_connection.return_value = pooled_connection

    with pytest.raises(RuntimeError, match="syntax error"):
        database.apply_schema(engine, script)

    pooled_connection.invalidate.assert_called_once()  # its state is unknown: never reused
    pooled_connection.close.assert_called_once()
