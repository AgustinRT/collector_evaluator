

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, Engine, create_engine, make_url

ENV_FILE = Path(__file__).parent.parent / ".env.persistence"

# Single source of the PostgreSQL schema (tables, sequences, enums and history triggers).
SCHEMA_SCRIPT = Path(__file__).resolve().parents[4] / "database" / "schema" / "schema.sql"

_DRIVER = "postgresql+psycopg"


class PostgresSettings(BaseSettings):
    """
    PostgreSQL connection settings, read from environment variables (POSTGRES_*)
    or, as a fallback, from ``.env.persistence``.
    """
    model_config = SettingsConfigDict(env_prefix="POSTGRES_", env_file=ENV_FILE, extra="ignore")

    host: str = "localhost"
    port: int = 5432
    db: str
    user: str
    password: SecretStr

    @property
    def url(self) -> URL:
        return URL.create(
            drivername=_DRIVER,
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.db,
        )


def to_psycopg_url(url: str | URL) -> URL:
    """
    Parses a PostgreSQL URL and makes it use the psycopg (v3) driver. Plain ``postgresql://`` and
    ``postgres://`` URLs would otherwise fail: SQLAlchemy would look for psycopg2, which is not installed.

    :raises ValueError: if the URL does not point to PostgreSQL.
    """
    url = make_url(url)
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername=_DRIVER)
    if url.get_backend_name() != "postgresql":
        raise ValueError(f"Expected a PostgreSQL URL, got '{url.drivername}://'.")
    return url


def create_postgres_engine(url: str | URL, connect_timeout: int) -> Engine:
    """
    Creates the engine without connecting; the first connection is opened on first use.
    """
    return create_engine(
        to_psycopg_url(url),
        pool_pre_ping=True,
        connect_args={"connect_timeout": connect_timeout},
    )


def apply_schema(engine: Engine, script: Path = SCHEMA_SCRIPT) -> None:
    """
    Runs the schema script on the database of ``engine``. The script is idempotent: it only creates what is
    missing and runs in its own transaction.
    """
    sql = script.read_text(encoding="utf-8")
    connection = engine.raw_connection()
    try:
        psycopg_connection = connection.driver_connection
        # The script manages its own transaction (BEGIN ... COMMIT). Without parameters, psycopg sends it
        # with the simple query protocol, which accepts several statements and does not treat "%" as a
        # placeholder (the script uses format('%I', ...)). SQLAlchemy's exec_driver_sql would do both.
        psycopg_connection.autocommit = True
        psycopg_connection.execute(sql)
        psycopg_connection.autocommit = False  # the connection goes back to the pool: restore the default
    except Exception:
        connection.invalidate()  # unknown state: never return it to the pool
        raise
    finally:
        connection.close()
