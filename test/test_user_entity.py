import pytest
from sqlalchemy import insert
from sqlalchemy.dialects import postgresql

from src.domain.enum.user_status import UserStatus
from src.domain.model.user import User
from src.infraestructure.persistence.entities.user_entity import UserEntity


# The location is optional, but when stored it must be complete and within range.
LOCATION_CHECKS = (
    "CONSTRAINT ck_user_location_complete CHECK ((latitude IS NULL) = (longitude IS NULL))",
    "CONSTRAINT ck_user_latitude_range CHECK (latitude BETWEEN -90 AND 90)",
    "CONSTRAINT ck_user_longitude_range CHECK (longitude BETWEEN -180 AND 180)",
)


def test_from_domain_copies_fields_and_leaves_id_to_the_database(alice):
    entity = UserEntity.from_domain(alice)

    assert entity.id is None
    assert (entity.username, entity.email) == ("alice", "alice@example.com")
    assert (entity.latitude, entity.longitude) == (40.4168, -3.7038)
    assert (entity.status, entity.evaluation) == (UserStatus.ACTIVE, 4.5)


def test_user_without_location_is_stored_with_null_coordinates():
    entity = UserEntity.from_domain(User(username="bob", email="bob@example.com"))

    assert (entity.latitude, entity.longitude) == (None, None)
    assert entity.to_domain().location is None


def test_to_domain_round_trip(alice):
    assert UserEntity.from_domain(alice).to_domain() == alice


def _users_table(ddl: list[str]) -> str:
    # "user" is a reserved word in PostgreSQL (quoted) but not in SQLite.
    return next(statement for statement in ddl if statement.startswith(('CREATE TABLE "user" ', "CREATE TABLE user ")))


def test_postgres_schema_takes_id_from_sequence_and_enforces_unique_username(schema_ddl):
    ddl = schema_ddl("postgresql+psycopg://")

    assert "CREATE SEQUENCE user_seq" in ddl
    assert "CREATE TYPE user_status AS ENUM ('deleted', 'in_progress', 'active', 'inactive', 'blocked')" in ddl
    create_table = _users_table(ddl)
    assert "id BIGINT NOT NULL" in create_table
    assert "username VARCHAR(150) NOT NULL" in create_table
    assert "email VARCHAR(254) NOT NULL" in create_table
    assert "latitude DOUBLE PRECISION, " in create_table
    assert "longitude DOUBLE PRECISION, " in create_table
    assert "CONSTRAINT uq_user_username UNIQUE (username)" in create_table
    for check in LOCATION_CHECKS:
        assert check in create_table
    # Database-side default, so rows inserted outside the application also use the sequence.
    assert """ALTER TABLE "user" ALTER COLUMN id SET DEFAULT nextval('user_seq')""" in ddl


def test_postgres_insert_takes_id_from_sequence():
    sql = str(insert(UserEntity).values(username="alice").compile(dialect=postgresql.dialect()))

    assert "nextval('user_seq')" in sql


def test_in_memory_schema_has_no_postgres_specific_objects(schema_ddl):
    ddl = schema_ddl("sqlite+pysqlite://")
    create_table = _users_table(ddl)

    assert not [statement for statement in ddl if "SEQUENCE" in statement or statement.startswith("ALTER")]
    assert create_table.startswith("CREATE TABLE user ( id INTEGER NOT NULL,")  # INTEGER PK auto-increments
    assert "email VARCHAR(254) NOT NULL" in create_table
    assert "CONSTRAINT uq_user_username UNIQUE (username)" in create_table
    for check in LOCATION_CHECKS:
        assert check in create_table


@pytest.mark.parametrize("status", list(UserStatus))
def test_status_is_stored_by_value_not_by_name(status):
    assert status.value in UserEntity.__table__.c.status.type.enums
