import pytest
from fastapi.testclient import TestClient

from main import app
from src.domain.enum.item_status import ItemStatus
from src.domain.model.item_collection import ItemCollection
from src.infraestructure.bootstrap.dependencies import get_db_session
from src.infraestructure.persistence.entities.item_collection_entity import ItemCollectionEntity
from src.infraestructure.persistence.entities.user_entity import UserEntity

BARCODE = 5050582500417
VALID = {"name": "Sample DVD", "description": "A DVD", "barcode": BARCODE}


@pytest.fixture
def stored_alice(alice):
    entity = UserEntity.from_domain(alice)
    entity.id = 1
    return entity


@pytest.fixture
def client(mock_session, stored_alice, database_assigns_ids):
    # Database with user "alice" and no items.
    mock_session.scalar.return_value = stored_alice
    mock_session.scalars.return_value = []
    # Only the DB session is replaced: router -> service -> real repositories is the real chain.
    app.dependency_overrides[get_db_session] = lambda: mock_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _errors(response) -> list[tuple[str, str]]:
    return [(".".join(map(str, error["loc"][1:])), error["type"]) for error in response.json()["detail"]]


# --- POST /users/{username}/items -----------------------------------------------------------------

def test_post_item_creates_it_for_the_user_and_starts_validating(client, mock_session, stored_alice):
    response = client.post("/users/alice/items", json={"name": " Sample DVD ", "description": "A DVD", "barcode": BARCODE})

    assert response.status_code == 201
    assert response.json() == {
        "id": 1, "name": "Sample DVD", "description": "A DVD", "barcode": BARCODE, "status": "validating",
        "owner": "alice",
    }
    (entity,), _ = mock_session.add.call_args
    assert isinstance(entity, ItemCollectionEntity)
    assert entity.owner is stored_alice
    assert entity.status is ItemStatus.VALIDATING
    mock_session.commit.assert_called_once()


def test_post_item_response_does_not_expose_owner_personal_data(client):
    body = client.post("/users/alice/items", json=VALID).json()

    assert "alice@example.com" not in str(body)


def test_post_item_for_unknown_user_returns_404(client, mock_session):
    mock_session.scalar.return_value = None

    response = client.post("/users/ghost/items", json=VALID)

    assert response.status_code == 404
    assert response.json() == {"detail": "User 'ghost' not found."}
    mock_session.add.assert_not_called()


@pytest.mark.parametrize("body, expected_errors", [
    ({"description": "A DVD", "barcode": BARCODE}, [("name", "missing")]),
    (VALID | {"name": "  "}, [("name", "string_too_short")]),
    (VALID | {"description": ""}, [("description", "string_too_short")]),
    (VALID | {"name": "n" * 201}, [("name", "string_too_long")]),
    ({"name": "Sample DVD", "description": "A DVD"}, [("barcode", "missing")]),
    (VALID | {"barcode": BARCODE + 1}, [("barcode", "value_error")]),
    (VALID | {"barcode": str(BARCODE)}, [("barcode", "int_type")]),
    (VALID | {"barcode": True}, [("barcode", "int_type")]),
    (VALID | {"barcode": 0}, [("barcode", "greater_than")]),
    (VALID | {"barcode": 10**14}, [("barcode", "less_than")]),
    (VALID | {"status": "able"}, [("status", "extra_forbidden")]),
    (VALID | {"owner": "bob"}, [("owner", "extra_forbidden")]),
])
def test_post_invalid_item_returns_422_without_touching_the_database(client, mock_session, body, expected_errors):
    response = client.post("/users/alice/items", json=body)

    assert response.status_code == 422
    assert _errors(response) == expected_errors
    mock_session.scalar.assert_not_called()
    mock_session.add.assert_not_called()


# --- GET /users/{username}/items ------------------------------------------------------------------

def test_get_items_lists_the_user_items(client, mock_session, stored_alice, alice):
    stored = [
        ItemCollectionEntity.from_domain(
            ItemCollection(name=name, description="d", barcode=barcode, owner=alice, status=status), stored_alice)
        for name, barcode, status in [("DVD", BARCODE, ItemStatus.VALIDATING), ("Book", 9780306406157, ItemStatus.ABLE)]
    ]
    for item_id, entity in enumerate(stored, start=1):
        entity.id = item_id
    mock_session.scalars.return_value = stored

    response = client.get("/users/alice/items")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "name": "DVD", "description": "d", "barcode": BARCODE, "status": "validating", "owner": "alice"},
        {"id": 2, "name": "Book", "description": "d", "barcode": 9780306406157, "status": "able", "owner": "alice"},
    ]


def test_get_items_of_user_without_items_is_empty(client):
    response = client.get("/users/alice/items")

    assert response.status_code == 200
    assert response.json() == []


def test_get_items_of_unknown_user_returns_404(client, mock_session):
    mock_session.scalar.return_value = None

    response = client.get("/users/ghost/items")

    assert response.status_code == 404
    assert response.json() == {"detail": "User 'ghost' not found."}
    mock_session.scalars.assert_not_called()
