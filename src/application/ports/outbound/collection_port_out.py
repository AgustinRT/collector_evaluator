

from typing import Protocol

from src.domain.model.collection import Collection


class CollectionPortOut(Protocol):
    """
    Outbound port: collection persistence required by the application, implemented by driven adapters.
    """

    def create_collection(self, collection: Collection) -> Collection:
        """
        Persists a new collection linked to its owner and items, and returns it as stored (with its id).

        :raises UserNotFoundError: if the owner is not stored.
        :raises ItemsNotFoundError: if some items are not stored for the owner.
        """
        ...

    def list_collections_by_owner(self, owner_username: str) -> list[Collection]:
        """
        Returns the stored collections of the user with that username, oldest first.
        """
        ...

    def list_collections_by_item(self, item_id: int) -> list[Collection]:
        """
        Returns the stored collections that include the item, oldest first.
        """
        ...
