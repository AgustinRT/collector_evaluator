

from collections.abc import Iterable

from src.domain.enum.item_status import ItemStatus


class ItemsNotFoundError(Exception):
    """
    Raised when some items do not exist or do not belong to the given user (both cases look the same,
    so other users' items are not revealed).
    """

    def __init__(self, username: str, item_ids: Iterable[int]):
        self.username = username
        self.item_ids = sorted(item_ids)
        noun = "Item" if len(self.item_ids) == 1 else "Items"
        super().__init__(f"{noun} {', '.join(map(str, self.item_ids))} not found for user '{username}'.")


class ItemsNotCollectableError(Exception):
    """
    Raised when some items cannot be added to a collection because of their status.
    """

    def __init__(self, statuses: dict[int, ItemStatus]):
        self.statuses = dict(sorted(statuses.items()))
        listed = ", ".join(f"{item_id} ({status.value})" for item_id, status in self.statuses.items())
        super().__init__(f"Items cannot be added to a collection because of their status: {listed}.")
