

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import StaticPool

IN_MEMORY_URL = "sqlite+pysqlite:///:memory:"


def create_in_memory_engine() -> Engine:
    """
    In-memory SQLite engine, used when PostgreSQL is unavailable. Its data lives only as long as the process.

    An in-memory SQLite database exists only within the connection that created it. StaticPool therefore
    shares that one connection between all sessions and request threads.
    """
    engine = create_engine(
        IN_MEMORY_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", enable_foreign_keys)
    return engine


def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    # SQLite ignores foreign keys unless enabled for each connection; PostgreSQL always enforces them.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
