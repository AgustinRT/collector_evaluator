

from src.application.ports.inbound.user_port_in import UserPortIn
from src.application.ports.outbound.user_port_out import UserPortOut
from src.domain.exception.user_exception import UserAlreadyExistsError, UserNotFoundError
from src.domain.model.user import User


class UserService(UserPortIn):
    """
    Implements the user use cases. Depends only on the outbound port, never on a concrete adapter.
    """

    def __init__(self, user_repository: UserPortOut):
        self._user_repository = user_repository

    def create_user(self, user_candidate: User) -> User:
        if self._user_repository.get_user(user_candidate.username) is not None:
            raise UserAlreadyExistsError(user_candidate.username)
        # Username, email and location come from the caller. Status and evaluation always start with the
        # domain defaults (IN_PROGRESS until validation completes, 0.0), whatever the candidate carries.
        # The check above does not cover two requests running at the same time; the repository
        # still reports that case as UserAlreadyExistsError (database unique constraint).
        new_user = User(
            username=user_candidate.username,
            email=user_candidate.email,
            location=user_candidate.location,
        )
        return self._user_repository.create_user(new_user)

    def get_user(self, username: str) -> User:
        user = self._user_repository.get_user(username)
        if user is None:
            raise UserNotFoundError(username)
        return user
