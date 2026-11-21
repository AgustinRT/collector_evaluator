

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from src.infraestructure.persistence.database_provider import DatabaseSettings, create_schema, provide_engine


def build_lifespan(
    database_settings: DatabaseSettings | None = None,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """
    Builds the application lifespan. On startup it selects the database engine (PostgreSQL, or the
    in-memory fallback), creates the schema and publishes the engine and session factory on ``app.state``.
    On shutdown it releases the engine.

    :param database_settings: explicit startup parameters. If None, they are read from the
        environment when the application starts.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = provide_engine(database_settings or DatabaseSettings())
        try:
            create_schema(engine)
            app.state.db_engine = engine
            app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
            yield
        finally:
            engine.dispose()

    return lifespan
