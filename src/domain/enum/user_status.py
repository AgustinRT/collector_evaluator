

from enum import Enum


class UserStatus(str, Enum):
    """
    Posible states for users
    """
    DELETED = "deleted"
    IN_PROGRESS = "in_progress"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
