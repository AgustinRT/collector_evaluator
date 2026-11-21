

from collections.abc import Iterable
from typing import Protocol

from src.domain.model.item_collection import ItemCollection


class ItemCollectionPortOut(Protocol):
    """
    Outbound port: item persistence required by the application, implemented by driven adapters.
    """

    def create_item(self, item: ItemCollection) -> ItemCollection:
        """
        Persists a new item linked to its owner and returns it as stored.

        :raises UserNotFoundError: if the owner is not stored.
        """
        ...

    def get_items(self, owner_username: str, item_ids: Iterable[int]) -> list[ItemCollection]:
        """
        Returns the stored items with those ids that belong to the user, ordered by id. Ids that do not
        exist or belong to another user are simply not returned.
        """
        ...

    def list_items_by_owner(self, owner_username: str) -> list[ItemCollection]:
        """
        Returns the stored items of the user with that username, oldest first.
        """
        ...
