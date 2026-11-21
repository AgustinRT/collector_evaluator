from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError

from src.application.ports.outbound.collection_port_out import CollectionPortOut
from src.application.ports.outbound.item_collection_port_out import ItemCollectionPortOut
from src.application.ports.outbound.user_port_out import UserPortOut
from src.application.use_cases.collection_service import CollectionService
from src.domain.enum.item_status import ItemStatus
from src.domain.enum.user_status import UserStatus
from src.domain.exception.item_exception import ItemsNotCollectableError, ItemsNotFoundError
from src.domain.exception.user_exception import UserCannotOwnCollectionsError, UserNotFoundError
from src.domain.model.collection import COLLECTABLE_ITEM_STATUSES, COLLECTION_OWNER_STATUSES, Collection
from src.domain.model.item_collection import ItemCollection

ELIGIBLE_USER = sorted(COLLECTION_OWNER_STATUSES)
INELIGIBLE_USER = sorted(set(UserStatus) - COLLECTION_OWNER_STATUSES)
ELIGIBLE_ITEM = sorted(COLLECTABLE_ITEM_STATUSES)
INELIGIBLE_ITEM = sorted(set(ItemStatus) - COLLECTABLE_ITEM_STATUSES)


@pytest.fixture
def owner(alice):
    return alice.model_copy(update={"status": UserStatus.IN_PROGRESS})


@pytest.fixture
def stored_items(owner):
    return {n: ItemCollection(id=n, name=f"Item {n}", description="d", barcode=5050582500417, owner=owner)
            for n in (1, 2, 3)}


@pytest.fixture
def user_port_out(owner):
    port = create_autospec(UserPortOut, instance=True)
    port.get_user.side_effect = lambda username: owner if username == owner.username else None
    return port


@pytest.fixture
def item_port_out(stored_items, owner):
    port = create_autospec(ItemCollectionPortOut, instance=True)
    port.get_items.side_effect = lambda username, ids: (
        [stored_items[i] for i in sorted(ids) if i in stored_items] if username == owner.username else [])
    return port


@pytest.fixture
def collection_port_out():
    port = create_autospec(CollectionPortOut, instance=True)
    port.create_collection.side_effect = lambda collection: collection.model_copy(update={"id": 10})
    port.list_collections_by_owner.return_value = []
    port.list_collections_by_item.return_value = []
    return port


@pytest.fixture
def service(collection_port_out, item_port_out, user_port_out):
    return CollectionService(collection_port_out, item_port_out, user_port_out)


# --- create ---------------------------------------------------------------------------------------

def test_create_collection_groups_the_user_items(service, collection_port_out, owner, stored_items):
    created = service.create_collection("alice", " Films ", "Favourites", [2, 1])

    (collection,), _ = collection_port_out.create_collection.call_args
    assert collection == Collection(name="Films", description="Favourites", owner=owner,
                                    items=[stored_items[1], stored_items[2]])
    assert created.id == 10


@pytest.mark.parametrize("status", ELIGIBLE_USER)
def test_eligible_user_statuses(service, owner, status):
    owner.status = status

    assert service.create_collection("alice", "Films", "d", [1]).id == 10


@pytest.mark.parametrize("status", INELIGIBLE_USER)
def test_ineligible_user_cannot_create_collections(service, collection_port_out, item_port_out, owner, status):
    owner.status = status

    with pytest.raises(UserCannotOwnCollectionsError) as exc_info:
        service.create_collection("alice", "Films", "d", [1])

    assert exc_info.value.status == status.value
    item_port_out.get_items.assert_not_called()
    collection_port_out.create_collection.assert_not_called()


def test_unknown_user(service, collection_port_out):
    with pytest.raises(UserNotFoundError):
        service.create_collection("ghost", "Films", "d", [1])

    collection_port_out.create_collection.assert_not_called()


def test_missing_or_foreign_items_are_reported_together(service, collection_port_out):
    with pytest.raises(ItemsNotFoundError) as exc_info:
        service.create_collection("alice", "Films", "d", [1, 99, 42])

    assert exc_info.value.item_ids == [42, 99]
    collection_port_out.create_collection.assert_not_called()


@pytest.mark.parametrize("status", ELIGIBLE_ITEM)
def test_eligible_item_statuses(service, stored_items, status):
    stored_items[1].status = status

    assert service.create_collection("alice", "Films", "d", [1]).id == 10


@pytest.mark.parametrize("status", INELIGIBLE_ITEM)
def test_ineligible_items_cannot_be_collected(service, collection_port_out, stored_items, status):
    stored_items[2].status = status

    with pytest.raises(ItemsNotCollectableError) as exc_info:
        service.create_collection("alice", "Films", "d", [1, 2])

    assert exc_info.value.statuses == {2: status}
    collection_port_out.create_collection.assert_not_called()


def test_invalid_collection_data_is_rejected(service, collection_port_out):
    with pytest.raises(ValidationError):
        service.create_collection("alice", "   ", "d", [1])

    collection_port_out.create_collection.assert_not_called()


# --- list -----------------------------------------------------------------------------------------

def test_list_collections(service, collection_port_out, owner, stored_items):
    stored = [Collection(id=1, name="Films", description="d", owner=owner, items=[stored_items[1]])]
    collection_port_out.list_collections_by_owner.return_value = stored

    assert service.list_collections("alice") == stored
    collection_port_out.list_collections_by_owner.assert_called_once_with("alice")


def test_list_collections_of_unknown_user(service, collection_port_out):
    with pytest.raises(UserNotFoundError):
        service.list_collections("ghost")

    collection_port_out.list_collections_by_owner.assert_not_called()


def test_list_item_collections(service, collection_port_out, owner, stored_items):
    stored = [Collection(id=1, name="Films", description="d", owner=owner, items=[stored_items[3]])]
    collection_port_out.list_collections_by_item.return_value = stored

    assert service.list_item_collections("alice", 3) == stored
    collection_port_out.list_collections_by_item.assert_called_once_with(3)


@pytest.mark.parametrize("username, item_id, error", [
    ("ghost", 1, UserNotFoundError),
    ("alice", 99, ItemsNotFoundError),   # missing, or belongs to another user
])
def test_list_item_collections_requires_an_own_item(service, collection_port_out, username, item_id, error):
    with pytest.raises(error):
        service.list_item_collections(username, item_id)

    collection_port_out.list_collections_by_item.assert_not_called()
