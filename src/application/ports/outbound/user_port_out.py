

from typing import Protocol

from src.domain.model.user import User


class UserPortOut(Protocol):
    """
    Outbound port: user persistence required by the application, implemented by driven adapters.
    """

    def create_user(self, user_candidate: User) -> User:
        """
        Persists a new user and returns it as stored.

        :raises UserAlreadyExistsError: if the username is already taken.
        """
        ...

    def get_user(self, username: str) -> User | None:
        """
        Returns the stored user with that username, or ``None`` if it does not exist.
        """
        ...
