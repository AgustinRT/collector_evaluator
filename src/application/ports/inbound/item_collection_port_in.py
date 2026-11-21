

from typing import Protocol

from src.domain.model.item_collection import ItemCollection


class ItemCollectionPortIn(Protocol):
    """
    Inbound port: item use cases offered to driving adapters (e.g. the REST API).
    """

    def create_item(self, owner_username: str, name: str, description: str, barcode: int) -> ItemCollection:
        """
        Validates a new item and registers it for the given user. The item is created with status VALIDATING.

        :raises UserNotFoundError: if the owner does not exist.
        :raises pydantic.ValidationError: if the item data is invalid (e.g. wrong barcode check digit).
        """
        ...

    def list_items(self, owner_username: str) -> list[ItemCollection]:
        """
        Returns the items of the given user, oldest first.

        :raises UserNotFoundError: if the user does not exist.
        """
        ...
