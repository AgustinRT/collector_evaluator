

from src.application.ports.inbound.collection_port_in import CollectionPortIn
from src.application.ports.outbound.collection_port_out import CollectionPortOut
from src.application.ports.outbound.item_collection_port_out import ItemCollectionPortOut
from src.application.ports.outbound.user_port_out import UserPortOut
from src.domain.exception.item_exception import ItemsNotCollectableError, ItemsNotFoundError
from src.domain.exception.user_exception import UserCannotOwnCollectionsError, UserNotFoundError
from src.domain.model.collection import COLLECTABLE_ITEM_STATUSES, COLLECTION_OWNER_STATUSES, Collection
from src.domain.model.item_collection import ItemCollection
from src.domain.model.user import User


class CollectionService(CollectionPortIn):
    """
    Implements the collection use cases. Depends only on outbound ports, never on concrete adapters.
    """

    def __init__(
        self,
        collection_repository: CollectionPortOut,
        item_repository: ItemCollectionPortOut,
        user_repository: UserPortOut,
    ):
        self._collection_repository = collection_repository
        self._item_repository = item_repository
        self._user_repository = user_repository

    def create_collection(self, owner_username: str, name: str, description: str, item_ids: list[int]) -> Collection:
        owner = self._get_user(owner_username)
        if owner.status not in COLLECTION_OWNER_STATUSES:
            raise UserCannotOwnCollectionsError(owner.username, owner.status.value)
        items = self._get_own_items(owner_username, item_ids)
        not_collectable = {item.id: item.status for item in items if item.status not in COLLECTABLE_ITEM_STATUSES}
        if not_collectable:
            raise ItemsNotCollectableError(not_collectable)
        # Building the domain object validates the rest (name, description, at least one item, no duplicates).
        collection = Collection(name=name, description=description, owner=owner, items=items)
        return self._collection_repository.create_collection(collection)

    def list_collections(self, owner_username: str) -> list[Collection]:
        self._get_user(owner_username)
        return self._collection_repository.list_collections_by_owner(owner_username)

    def list_item_collections(self, owner_username: str, item_id: int) -> list[Collection]:
        self._get_user(owner_username)
        self._get_own_items(owner_username, [item_id])
        return self._collection_repository.list_collections_by_item(item_id)

    def _get_user(self, username: str) -> User:
        user = self._user_repository.get_user(username)
        if user is None:
            raise UserNotFoundError(username)
        return user

    def _get_own_items(self, owner_username: str, item_ids: list[int]) -> list[ItemCollection]:
        items = self._item_repository.get_items(owner_username, item_ids)
        missing = set(item_ids) - {item.id for item in items}
        if missing:
            raise ItemsNotFoundError(owner_username, missing)
        return items
