import pytest
from fastapi.testclient import TestClient

from main import app
from src.domain.enum.item_status import ItemStatus
from src.domain.enum.user_status import UserStatus
from src.domain.model.item_collection import ItemCollection
from src.infraestructure.bootstrap.dependencies import get_db_session
from src.infraestructure.persistence.entities.collection_entity import CollectionEntity
from src.infraestructure.persistence.entities.item_collection_entity import ItemCollectionEntity
from src.infraestructure.persistence.entities.user_entity import UserEntity

VALID = {"name": "Films", "description": "Favourites", "item_ids": [1, 2]}


@pytest.fixture
def stored_alice(alice):
    entity = UserEntity.from_domain(alice.model_copy(update={"status": UserStatus.IN_PROGRESS}))
    entity.id = 1
    return entity


@pytest.fixture
def stored_items(alice, stored_alice):
    entities = []
    for item_id in (1, 2):
        entity = ItemCollectionEntity.from_domain(
            ItemCollection(name=f"Item {item_id}", description="d", barcode=5050582500417, owner=alice), stored_alice)
        entity.id = item_id
        entities.append(entity)
    return entities


@pytest.fixture
def client(database_assigns_ids, stored_alice, stored_items):
    # Database with user "alice" owning items 1 and 2, and no collections yet.
    session = database_assigns_ids
    session.scalar.return_value = stored_alice
    session.scalars.return_value = stored_items
    # Only the DB session is replaced: router -> service -> real repositories is the real chain.
    app.dependency_overrides[get_db_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _errors(response) -> list[tuple[str, str]]:
    return [(".".join(map(str, error["loc"][1:])), error["type"]) for error in response.json()["detail"]]


def _item_json(item_id: int, status: str = "validating") -> dict:
    return {"id": item_id, "name": f"Item {item_id}", "description": "d", "barcode": 5050582500417,
            "status": status, "owner": "alice"}


# --- POST /users/{username}/collections -----------------------------------------------------------

def test_post_collection_groups_the_user_items(client, mock_session, stored_alice, stored_items):
    response = client.post("/users/alice/collections", json={**VALID, "name": "  Films "})

    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "Films", "description": "Favourites", "owner": "alice",
                                "items": [_item_json(1), _item_json(2)]}
    (entity,), _ = mock_session.add.call_args
    assert entity.owner is stored_alice
    assert entity.items == stored_items
    mock_session.commit.assert_called_once()


def test_post_collection_for_unknown_user_returns_404(client, mock_session):
    mock_session.scalar.return_value = None

    response = client.post("/users/ghost/collections", json=VALID)

    assert response.status_code == 404
    assert response.json() == {"detail": "User 'ghost' not found."}


def test_post_collection_with_items_not_owned_returns_404(client, mock_session, stored_items):
    mock_session.scalars.return_value = stored_items[:1]  # item 2 is missing or belongs to another user

    response = client.post("/users/alice/collections", json=VALID)

    assert response.status_code == 404
    assert response.json() == {"detail": "Item 2 not found for user 'alice'."}
    mock_session.add.assert_not_called()


def test_post_collection_by_blocked_user_returns_409(client, mock_session, stored_alice):
    stored_alice.status = UserStatus.BLOCKED

    response = client.post("/users/alice/collections", json=VALID)

    assert response.status_code == 409
    assert response.json() == {"detail": "User 'alice' cannot create collections while its status is 'blocked'."}
    mock_session.add.assert_not_called()


def test_post_collection_with_disabled_item_returns_409(client, mock_session, stored_items):
    stored_items[1].status = ItemStatus.DISABLE

    response = client.post("/users/alice/collections", json=VALID)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Items cannot be added to a collection because of their status: 2 (disable)."}
    mock_session.add.assert_not_called()


@pytest.mark.parametrize("body, expected_errors", [
    ({"description": "d", "item_ids": [1]}, [("name", "missing")]),
    (VALID | {"name": "   "}, [("name", "string_too_short")]),
    (VALID | {"name": "n" * 201}, [("name", "string_too_long")]),
    ({"name": "Films", "item_ids": [1]}, [("description", "missing")]),
    ({"name": "Films", "description": "d"}, [("item_ids", "missing")]),
    (VALID | {"item_ids": []}, [("item_ids", "too_short")]),
    (VALID | {"item_ids": [1, 2, 1]}, [("item_ids", "value_error")]),
    (VALID | {"item_ids": ["1"]}, [("item_ids.0", "int_type")]),
    (VALID | {"item_ids": [True]}, [("item_ids.0", "int_type")]),
    (VALID | {"item_ids": [0]}, [("item_ids.0", "greater_than")]),
    (VALID | {"owner": "bob"}, [("owner", "extra_forbidden")]),
])
def test_post_invalid_collection_returns_422_without_touching_the_database(client, mock_session, body, expected_errors):
    response = client.post("/users/alice/collections", json=body)

    assert response.status_code == 422
    assert _errors(response) == expected_errors
    mock_session.scalar.assert_not_called()
    mock_session.add.assert_not_called()


# --- GET /users/{username}/collections and /users/{username}/items/{item_id}/collections -----------

@pytest.fixture
def stored_collections(stored_alice, stored_items):
    return [
        CollectionEntity(id=1, name="Films", description="Favourites", owner=stored_alice, items=stored_items),
        CollectionEntity(id=2, name="Films", description="Same name", owner=stored_alice, items=stored_items[:1]),
    ]


def test_get_collections_lists_them_with_their_items(client, mock_session, stored_items, stored_collections):
    # The user check uses session.scalar (alice); the collections query uses session.scalars.
    mock_session.scalars.return_value = stored_collections

    response = client.get("/users/alice/collections")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "name": "Films", "description": "Favourites", "owner": "alice", "items": [_item_json(1), _item_json(2)]},
        {"id": 2, "name": "Films", "description": "Same name", "owner": "alice", "items": [_item_json(1)]},
    ]


def test_get_collections_of_user_without_collections(client, mock_session):
    mock_session.scalars.return_value = []

    assert client.get("/users/alice/collections").json() == []


@pytest.mark.parametrize("path", ["/users/ghost/collections", "/users/ghost/items/1/collections"])
def test_get_collections_of_unknown_user_returns_404(client, mock_session, path):
    mock_session.scalar.return_value = None

    response = client.get(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "User 'ghost' not found."}


def test_get_item_collections(client, mock_session, stored_items, stored_collections):
    # First query: the item check (must be alice's); second: the collections that include it.
    mock_session.scalars.side_effect = [stored_items[1:], stored_collections[:1]]

    response = client.get("/users/alice/items/2/collections")

    assert response.status_code == 200
    assert [collection["id"] for collection in response.json()] == [1]


def test_get_collections_of_item_not_owned_returns_404(client, mock_session):
    mock_session.scalars.return_value = []

    response = client.get("/users/alice/items/7/collections")

    assert response.status_code == 404
    assert response.json() == {"detail": "Item 7 not found for user 'alice'."}


@pytest.mark.parametrize("item_id", ["0", "-1", "abc"])
def test_get_item_collections_with_invalid_item_id_returns_422(client, mock_session, item_id):
    assert client.get(f"/users/alice/items/{item_id}/collections").status_code == 422
    mock_session.scalar.assert_not_called()
