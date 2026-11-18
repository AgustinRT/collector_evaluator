

from enum import Enum


class ItemStatus(str, Enum):
    DELETED = "deleted"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    ABLE = "able"
    DISABLE = "disable"
