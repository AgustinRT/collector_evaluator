

from src.application.ports.inbound.item_collection_port_in import ItemCollectionPortIn
from src.application.ports.outbound.item_collection_port_out import ItemCollectionPortOut
from src.application.ports.outbound.user_port_out import UserPortOut
from src.domain.exception.user_exception import UserNotFoundError
from src.domain.model.item_collection import ItemCollection
from src.domain.model.user import User


class ItemCollectionService(ItemCollectionPortIn):
    """
    Implements the item use cases. Depends only on outbound ports, never on concrete adapters.
    """

    def __init__(self, item_repository: ItemCollectionPortOut, user_repository: UserPortOut):
        self._item_repository = item_repository
        self._user_repository = user_repository

    def create_item(self, owner_username: str, name: str, description: str, barcode: int) -> ItemCollection:
        owner = self._get_owner(owner_username)
        # Building the domain object validates the item. The status is not chosen by the caller:
        # every new item starts with the domain default (VALIDATING).
        item = ItemCollection(name=name, description=description, barcode=barcode, owner=owner)
        return self._item_repository.create_item(item)

    def list_items(self, owner_username: str) -> list[ItemCollection]:
        # Distinguishes "unknown user" (error) from "user without items" (empty list).
        self._get_owner(owner_username)
        return self._item_repository.list_items_by_owner(owner_username)

    def _get_owner(self, username: str) -> User:
        owner = self._user_repository.get_user(username)
        if owner is None:
            raise UserNotFoundError(username)
        return owner
