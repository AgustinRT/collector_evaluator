

import sqlite3

from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.application.ports.outbound.user_port_out import UserPortOut
from src.domain.exception.user_exception import UserAlreadyExistsError
from src.domain.model.user import User
from src.infraestructure.persistence.entities.user_entity import UserEntity


def _is_unique_violation(driver_error: BaseException | None) -> bool:
    # PostgreSQL (psycopg) in normal operation; SQLite when running on the in-memory fallback.
    return isinstance(driver_error, UniqueViolation) or (
        isinstance(driver_error, sqlite3.IntegrityError)
        and driver_error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE
    )


class SqlAlchemyUserRepository(UserPortOut):
    """
    Persistence adapter for the user outbound port, using SQLAlchemy (psycopg driver on PostgreSQL).
    """

    def __init__(self, session: Session):
        self._session = session

    def create_user(self, user_candidate: User) -> User:
        entity = UserEntity.from_domain(user_candidate)
        self._session.add(entity)
        try:
            # Each creation is its own unit of work, so it is committed here. This guarantees the
            # user is stored before the caller gets a response.
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            # The unique constraint is the source of truth for duplicates, so concurrent requests
            # cannot create the same user twice.
            if _is_unique_violation(exc.orig):
                raise UserAlreadyExistsError(user_candidate.username) from exc
            raise
        return entity.to_domain()

    def get_user(self, username: str) -> User | None:
        entity = self._session.scalar(select(UserEntity).where(UserEntity.username == username))
        return entity.to_domain() if entity is not None else None
