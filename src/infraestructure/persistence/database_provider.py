

import logging

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, Engine, inspect
from sqlalchemy.exc import OperationalError

from src.infraestructure.persistence.entities.base import Base
from src.infraestructure.persistence.in_memory.database import create_in_memory_engine
from src.infraestructure.persistence.postgresql.database import (
    ENV_FILE,
    PostgresSettings,
    SCHEMA_SCRIPT,
    apply_schema,
    create_postgres_engine,
    to_psycopg_url,
)

logger = logging.getLogger(__name__)


class OutdatedSchemaError(RuntimeError):
    """
    An existing table lacks columns the entities need (it was created by an older version).
    """


class DatabaseSettings(BaseSettings):
    """
    Startup parameters that choose the database. They come from explicit arguments (CLI / create_app),
    then DATABASE_* environment variables, then ``.env.persistence``.
    """
    model_config = SettingsConfigDict(env_prefix="DATABASE_", env_file=ENV_FILE, extra="ignore")

    url: SecretStr | None = None
    """Full PostgreSQL URL. If not set, it is built from the POSTGRES_* settings."""
    name: str | None = None
    """Database name to use on the chosen server. Overrides the one in the URL / POSTGRES_DB."""
    fallback_to_memory: bool = True
    """If PostgreSQL is unavailable at startup, use an in-memory SQLite database instead of failing."""
    connect_timeout: int = 5
    """Seconds to wait for PostgreSQL before treating it as unavailable."""


def resolve_postgres_url(settings: DatabaseSettings) -> URL:
    """
    :raises pydantic.ValidationError: if no URL is given and the POSTGRES_* settings are incomplete.
    """
    url = settings.url.get_secret_value() if settings.url is not None else PostgresSettings().url
    url = to_psycopg_url(url)
    return url.set(database=settings.name) if settings.name else url


def provide_engine(settings: DatabaseSettings) -> Engine:
    """
    Returns an engine for the configured PostgreSQL database. If PostgreSQL is unreachable or not
    configured, returns an in-memory engine instead (unless ``fallback_to_memory`` is disabled).
    """
    try:
        engine = create_postgres_engine(resolve_postgres_url(settings), settings.connect_timeout)
        try:
            with engine.connect():
                pass
        except OperationalError:
            engine.dispose()
            raise
    except (OperationalError, ValidationError) as exc:
        if not settings.fallback_to_memory:
            raise
        reason = str(getattr(exc, "orig", None) or exc).strip().splitlines()[0]
        logger.warning(
            "PostgreSQL is unavailable (%s). Falling back to an in-memory database: "
            "data will be lost when the application stops.", reason,
        )
        return create_in_memory_engine()

    logger.info("Using database %s", engine.url.render_as_string(hide_password=True))
    return engine


def create_schema(engine: Engine) -> None:
    """
    Creates the missing tables, sequences and types. Existing objects are left untouched.

    On PostgreSQL the schema comes from database/schema/schema.sql, which also creates the history tables and
    triggers. Elsewhere (the in-memory SQLite fallback) it is created from the entities, without history.

    :raises OutdatedSchemaError: if an existing table lacks columns the entities need.
    """
    # Import the entities so they are registered in Base.metadata.
    from src.infraestructure.persistence.entities import (  # noqa: F401
        collection_entity,
        item_collection_entity,
        user_entity,
    )

    if engine.dialect.name == "postgresql":
        apply_schema(engine)
        logger.info("Database schema applied from %s", SCHEMA_SCRIPT)
    else:
        Base.metadata.create_all(engine)
    _verify_columns(engine)


def _verify_columns(engine: Engine) -> None:
    # create_all never alters an existing table. Without this check, a table created by an older
    # version would let the application start and then fail on every query.
    inspector = inspect(engine)
    problems = []
    for table in Base.metadata.sorted_tables:
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        missing = [column.name for column in table.columns if column.name not in existing]
        if missing:
            problems.append(f"table '{table.name}' is missing columns {missing}")
    if problems:
        raise OutdatedSchemaError(
            "The database schema is outdated: " + "; ".join(problems)
            + ". Existing tables are never altered automatically: migrate them or recreate them."
        )
