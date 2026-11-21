

from sqlalchemy import DDL, Sequence, Table, event
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Declarative base for every persistence entity. Engine-agnostic: shared by PostgreSQL and the
    in-memory fallback.
    """


def use_sequence_as_postgres_default(table: Table, column: str, sequence: Sequence) -> None:
    """
    Makes ``sequence`` the server-side default of ``table.column`` on PostgreSQL, so rows inserted
    outside the application also get their id from it.

    A plain ``server_default=nextval(...)`` cannot be used because it would break table creation on
    SQLite (in-memory fallback), so this runs only on PostgreSQL, right after the table is created.
    """
    event.listen(
        table,
        "after_create",
        # %(table)s is filled in by SQLAlchemy with the table name quoted when needed (e.g. "user").
        DDL(f"ALTER TABLE %(table)s ALTER COLUMN {column} SET DEFAULT nextval('{sequence.name}')")
        .execute_if(dialect="postgresql"),
    )
