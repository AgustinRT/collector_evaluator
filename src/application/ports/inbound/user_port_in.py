

from typing import Protocol

from src.domain.model.user import User


class UserPortIn(Protocol):
    """
    Inbound port: user use cases offered to driving adapters (e.g. the REST API).
    """

    def create_user(self, user_candidate: User) -> User:
        """
        Registers a new user. Only the candidate's username, email and location are used: the user
        is created with status IN_PROGRESS and evaluation 0.0.

        :raises UserAlreadyExistsError: if the username is already taken.
        """
        ...

    def get_user(self, username: str) -> User:
        """
        Returns the user identified by ``username``.

        :raises UserNotFoundError: if no user has that username.
        """
        ...
