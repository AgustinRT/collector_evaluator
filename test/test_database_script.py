"""
Checks database/init.sql and database/schema/schema.sql against the entities and domain enums, without a database.
(The script was also verified on PostgreSQL 16: same columns, types, constraints and indexes as the entities.)
"""
import re
from pathlib import Path

import pytest
from sqlalchemy import Sequence

from src.domain.enum.item_status import ItemStatus
from src.domain.enum.user_status import UserStatus
from src.infraestructure.persistence.entities import collection_entity, item_collection_entity, user_entity  # noqa: F401
from src.infraestructure.persistence.entities.base import Base
from src.infraestructure.persistence.postgresql.database import SCHEMA_SCRIPT

ROOT = Path(__file__).resolve().parent.parent
INIT_SCRIPT = ROOT / "database" / "init.sql"
SCHEMA = SCHEMA_SCRIPT.read_text(encoding="utf-8")
TABLES = list(Base.metadata.sorted_tables)
SEQUENCED_TABLES = [table for table in TABLES if "id" in table.c and isinstance(table.c.id.default, Sequence)]
HISTORY_COLUMNS = ["history_id", "operation", "changed_at", "changed_by"]


def _quoted(name: str) -> str:
    return f'"{name}"' if name == "user" else name  # "user" is a reserved word in PostgreSQL


def _columns_of(table_name: str) -> list[str]:
    """
    Column names declared in the script's CREATE TABLE of ``table_name`` (constraint lines excluded).
    """
    match = re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(table_name)} \((.*?)\n\);", SCHEMA, re.S)
    assert match, f"schema.sql does not create table {table_name}"
    lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    return [line.split()[0] for line in lines
            if not line.startswith(("PRIMARY KEY", "CONSTRAINT", "FOREIGN KEY", "REFERENCES", "--"))]


def _enum_values(name: str) -> list[str]:
    match = re.search(rf"CREATE TYPE {name} AS ENUM \(([^)]*)\)", SCHEMA)
    assert match, f"schema.sql does not create enum {name}"
    return re.findall(r"'([^']*)'", match.group(1))


@pytest.mark.parametrize("table", TABLES, ids=[table.name for table in TABLES])
def test_script_creates_every_entity_table_with_its_columns(table):
    assert _columns_of(_quoted(table.name)) == [column.name for column in table.columns]


@pytest.mark.parametrize("table", SEQUENCED_TABLES, ids=[table.name for table in SEQUENCED_TABLES])
def test_ids_come_from_the_entity_sequence(table):
    sequence = table.c.id.default.name
    assert f"CREATE SEQUENCE IF NOT EXISTS {sequence};" in SCHEMA
    assert re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(_quoted(table.name))} \(\s*id\s+bigint\s+NOT NULL "
                     rf"DEFAULT nextval\('{sequence}'\)", SCHEMA)
    assert f"ALTER SEQUENCE {sequence} OWNED BY {_quoted(table.name)}.id;" in SCHEMA


def test_requested_sequence_names():
    assert {"user_seq", "item_collection_seq", "collection_seq"} <= set(
        re.findall(r"CREATE SEQUENCE IF NOT EXISTS (\w+);", SCHEMA))


@pytest.mark.parametrize("name, enum", [("user_status", UserStatus), ("item_status", ItemStatus)])
def test_enums_match_the_domain(name, enum):
    assert _enum_values(name) == [member.value for member in enum]


@pytest.mark.parametrize("table", TABLES, ids=[table.name for table in TABLES])
def test_every_table_has_a_history_table_and_trigger(table):
    assert _columns_of(f"{table.name}_history") == HISTORY_COLUMNS + [column.name for column in table.columns]
    assert re.search(rf"CREATE OR REPLACE TRIGGER {table.name}_history\s+AFTER INSERT OR UPDATE OR DELETE ON "
                     rf"{re.escape(_quoted(table.name))}\s+FOR EACH ROW EXECUTE FUNCTION record_history\(\);", SCHEMA)


def test_history_operations():
    assert _enum_values("history_operation") == ["INSERT", "UPDATE", "DELETE"]


def test_schema_is_idempotent_and_transactional():
    creates = [line for line in SCHEMA.splitlines() if line.startswith("CREATE ")]
    assert len(creates) >= 20
    for line in creates:
        assert "IF NOT EXISTS" in line or line.startswith("CREATE OR REPLACE "), f"not idempotent: {line}"
    # CREATE TYPE has no IF NOT EXISTS: each one must be guarded.
    assert SCHEMA.count("CREATE TYPE") == SCHEMA.count("EXCEPTION WHEN duplicate_object THEN NULL;") == 3
    assert "DROP " not in SCHEMA and "TRUNCATE" not in SCHEMA
    body = [line for line in SCHEMA.splitlines() if line.strip() and not line.startswith("--")]
    assert body[0] == "BEGIN;" and body[-1] == "COMMIT;"
    assert "pg_advisory_xact_lock" in SCHEMA  # concurrent runs (several app instances) are serialized


def test_init_script_creates_the_database_and_includes_the_schema():
    init = INIT_SCRIPT.read_text(encoding="utf-8")

    assert "\\set ON_ERROR_STOP on" in init
    assert "CREATE DATABASE collector_evaluator ENCODING ''UTF8''" in init
    assert "WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'collector_evaluator')" in init
    assert "\\connect collector_evaluator" in init
    included = re.search(r"^\\ir (\S+)$", init, re.M).group(1)
    assert (INIT_SCRIPT.parent / included).resolve() == SCHEMA_SCRIPT
