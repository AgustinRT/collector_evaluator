from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError

from src.application.ports.outbound.item_collection_port_out import ItemCollectionPortOut
from src.application.ports.outbound.user_port_out import UserPortOut
from src.application.use_cases.item_collection_service import ItemCollectionService
from src.domain.enum.item_status import ItemStatus
from src.domain.exception.user_exception import UserNotFoundError
from src.domain.model.item_collection import ItemCollection

BARCODE = 5050582500417


@pytest.fixture
def user_port_out(alice):
    port = create_autospec(UserPortOut, instance=True)
    port.get_user.side_effect = lambda username: alice if username == "alice" else None
    return port


@pytest.fixture
def item_port_out():
    port = create_autospec(ItemCollectionPortOut, instance=True)
    port.create_item.side_effect = lambda item: item
    port.list_items_by_owner.return_value = []
    return port


@pytest.fixture
def service(item_port_out, user_port_out):
    return ItemCollectionService(item_port_out, user_port_out)


def test_create_item_links_it_to_its_owner_and_starts_validating(service, item_port_out, alice):
    created = service.create_item("alice", " Sample DVD ", "A DVD", BARCODE)

    expected = ItemCollection(
        name="Sample DVD", description="A DVD", barcode=BARCODE, owner=alice, status=ItemStatus.VALIDATING,
    )
    item_port_out.create_item.assert_called_once_with(expected)
    assert created == expected


def test_create_item_for_unknown_user_fails_without_persisting(service, item_port_out):
    with pytest.raises(UserNotFoundError) as exc_info:
        service.create_item("ghost", "Sample DVD", "A DVD", BARCODE)

    assert exc_info.value.username == "ghost"
    item_port_out.create_item.assert_not_called()


def test_create_item_with_invalid_barcode_fails_without_persisting(service, item_port_out):
    with pytest.raises(ValidationError, match="invalid check digit"):
        service.create_item("alice", "Sample DVD", "A DVD", BARCODE + 1)

    item_port_out.create_item.assert_not_called()


def test_list_items_returns_the_owner_items(service, item_port_out, alice):
    items = [ItemCollection(name=f"Item {n}", description="d", barcode=BARCODE, owner=alice) for n in range(2)]
    item_port_out.list_items_by_owner.return_value = items

    assert service.list_items("alice") == items
    item_port_out.list_items_by_owner.assert_called_once_with("alice")


def test_list_items_of_user_without_items_is_empty(service):
    assert service.list_items("alice") == []


def test_list_items_of_unknown_user_fails(service, item_port_out):
    with pytest.raises(UserNotFoundError):
        service.list_items("ghost")

    item_port_out.list_items_by_owner.assert_not_called()
