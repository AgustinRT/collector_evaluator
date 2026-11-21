import sqlite3

import pytest
from psycopg.errors import NotNullViolation, UniqueViolation
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from src.domain.exception.user_exception import UserAlreadyExistsError
from src.infraestructure.persistence.entities.user_entity import UserEntity
from src.infraestructure.persistence.repositories.user_repository import SqlAlchemyUserRepository


def _integrity_error(orig: Exception) -> IntegrityError:
    return IntegrityError('INSERT INTO "user" ...', {}, orig)


def _sqlite_error(message: str, error_code: int) -> sqlite3.IntegrityError:
    error = sqlite3.IntegrityError(message)
    error.sqlite_errorcode = error_code
    return error


def test_create_user_adds_entity_commits_and_returns_domain_user(mock_session, alice):
    created = SqlAlchemyUserRepository(mock_session).create_user(alice)

    (entity,), _ = mock_session.add.call_args
    assert isinstance(entity, UserEntity)
    assert entity.id is None
    assert (entity.username, entity.email, entity.latitude, entity.longitude) == (
        "alice", "alice@example.com", 40.4168, -3.7038)
    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_not_called()
    assert created == alice


@pytest.mark.parametrize("driver_error", [
    UniqueViolation("duplicate key value violates unique constraint"),
    _sqlite_error("UNIQUE constraint failed: users.username", sqlite3.SQLITE_CONSTRAINT_UNIQUE),
], ids=["postgresql", "in_memory_sqlite"])
def test_create_user_translates_unique_violation_into_domain_error(mock_session, alice, driver_error):
    mock_session.commit.side_effect = _integrity_error(driver_error)

    with pytest.raises(UserAlreadyExistsError) as exc_info:
        SqlAlchemyUserRepository(mock_session).create_user(alice)

    assert exc_info.value.username == "alice"
    mock_session.rollback.assert_called_once()


@pytest.mark.parametrize("driver_error", [
    NotNullViolation("null value in column"),
    _sqlite_error("NOT NULL constraint failed: users.status", sqlite3.SQLITE_CONSTRAINT_NOTNULL),
], ids=["postgresql", "in_memory_sqlite"])
def test_create_user_reraises_other_integrity_errors(mock_session, alice, driver_error):
    mock_session.commit.side_effect = _integrity_error(driver_error)

    with pytest.raises(IntegrityError):
        SqlAlchemyUserRepository(mock_session).create_user(alice)

    mock_session.rollback.assert_called_once()


def test_get_user_queries_by_username_and_maps_to_domain(mock_session, alice):
    stored = UserEntity.from_domain(alice)
    stored.id = 7
    mock_session.scalar.return_value = stored

    found = SqlAlchemyUserRepository(mock_session).get_user("alice")

    assert found == alice
    (statement,), _ = mock_session.scalar.call_args
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert 'FROM "user"' in sql
    assert """WHERE "user".username = 'alice'""" in sql


def test_get_user_returns_none_when_missing(mock_session):
    mock_session.scalar.return_value = None

    assert SqlAlchemyUserRepository(mock_session).get_user("ghost") is None
