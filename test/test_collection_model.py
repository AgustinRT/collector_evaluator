import pytest
from pydantic import ValidationError

from src.domain.enum.item_status import ItemStatus
from src.domain.model.collection import Collection
from src.domain.model.item_collection import ItemCollection
from src.domain.model.user import User


@pytest.fixture
def items(alice):
    return [ItemCollection(id=n, name=f"Item {n}", description="d", barcode=5050582500417, owner=alice)
            for n in (1, 2)]


@pytest.fixture
def valid_fields(alice, items):
    return {"name": "Films", "description": "Favourites", "owner": alice, "items": items}


def _error_types(exc_info) -> list[tuple[tuple, str]]:
    return [(error["loc"], error["type"]) for error in exc_info.value.errors()]


def test_valid_collection(valid_fields, items):
    collection = Collection(**valid_fields | {"name": "  Films ", "description": " Favourites "})

    assert (collection.id, collection.name, collection.description) == (None, "Films", "Favourites")
    assert collection.items == items


@pytest.mark.parametrize("missing", ["name", "description", "owner", "items"])
def test_mandatory_fields(valid_fields, missing):
    del valid_fields[missing]

    with pytest.raises(ValidationError) as exc_info:
        Collection(**valid_fields)

    assert _error_types(exc_info) == [((missing,), "missing")]


@pytest.mark.parametrize("field, value, error_type", [
    ("name", "  ", "string_too_short"),
    ("name", "n" * 201, "string_too_long"),
    ("description", "", "string_too_short"),
    ("description", "d" * 2001, "string_too_long"),
    ("items", [], "too_short"),
])
def test_invalid_fields(valid_fields, field, value, error_type):
    with pytest.raises(ValidationError) as exc_info:
        Collection(**valid_fields | {field: value})

    assert _error_types(exc_info) == [((field,), error_type)]


def test_items_must_belong_to_the_owner(valid_fields, items):
    bob = User(username="bob", email="bob@example.com")
    foreign = items[1].model_copy(update={"owner": bob})

    with pytest.raises(ValidationError, match=r"items \[2\] do not belong to user 'alice'"):
        Collection(**valid_fields | {"items": [items[0], foreign]})


def test_an_item_cannot_appear_twice(valid_fields, items):
    with pytest.raises(ValidationError, match="an item cannot appear twice"):
        Collection(**valid_fields | {"items": [items[0], items[0]]})


@pytest.mark.parametrize("status", list(ItemStatus))
def test_item_status_does_not_affect_an_existing_collection(valid_fields, items, status):
    # Statuses are checked when creating a collection (use case), not by the model: a collection must stay
    # readable after one of its items is disabled or deleted.
    items[0] = items[0].model_copy(update={"status": status})

    assert Collection(**valid_fields | {"items": items}).items[0].status is status
