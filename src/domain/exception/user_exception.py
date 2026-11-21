

class UserAlreadyExistsError(Exception):
    """
    Raised when trying to create a user whose username is already taken.
    """

    def __init__(self, username: str):
        self.username = username
        super().__init__(f"User '{username}' already exists.")


class UserNotFoundError(Exception):
    """
    Raised when a requested user does not exist.
    """

    def __init__(self, username: str):
        self.username = username
        super().__init__(f"User '{username}' not found.")


class UserCannotOwnCollectionsError(Exception):
    """
    Raised when a user's status does not allow creating collections (e.g. blocked or deleted).
    """

    def __init__(self, username: str, status: str):
        self.username = username
        self.status = status
        super().__init__(f"User '{username}' cannot create collections while its status is '{status}'.")
