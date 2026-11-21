

from typing import Protocol

from src.domain.model.collection import Collection


class CollectionPortIn(Protocol):
    """
    Inbound port: collection use cases offered to driving adapters (e.g. the REST API).
    """

    def create_collection(self, owner_username: str, name: str, description: str, item_ids: list[int]) -> Collection:
        """
        Groups one or more items of the user into a new collection.

        :raises UserNotFoundError: if the user does not exist.
        :raises UserCannotOwnCollectionsError: if the user's status does not allow it.
        :raises ItemsNotFoundError: if some items do not exist or belong to another user.
        :raises ItemsNotCollectableError: if some items' status does not allow it.
        :raises pydantic.ValidationError: if the collection data is invalid.
        """
        ...

    def list_collections(self, owner_username: str) -> list[Collection]:
        """
        Returns the collections of the user, oldest first.

        :raises UserNotFoundError: if the user does not exist.
        """
        ...

    def list_item_collections(self, owner_username: str, item_id: int) -> list[Collection]:
        """
        Returns the collections that include the given item of the user, oldest first.

        :raises UserNotFoundError: if the user does not exist.
        :raises ItemsNotFoundError: if the item does not exist or belongs to another user.
        """
        ...
