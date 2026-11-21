import pytest
from fastapi.testclient import TestClient
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError

from main import app
from src.domain.enum.user_status import UserStatus
from src.infraestructure.bootstrap.dependencies import get_db_session
from src.infraestructure.persistence.entities.user_entity import UserEntity

VALID = {"username": "alice", "email": "alice@example.com"}
MADRID = {"latitude": 40.4168, "longitude": -3.7038}


@pytest.fixture
def client(mock_session):
    # Start from an empty database: no user is found by username.
    mock_session.scalar.return_value = None
    # Only the DB session is replaced: router -> UserService -> SqlAlchemyUserRepository is the real chain.
    app.dependency_overrides[get_db_session] = lambda: mock_session
    # Not used as a context manager, so the lifespan (engine selection, schema creation) does not run.
    yield TestClient(app)
    app.dependency_overrides.clear()


def _stored(username: str, **fields) -> UserEntity:
    defaults = {"email": f"{username}@example.com", "latitude": None, "longitude": None,
                "status": UserStatus.ACTIVE, "evaluation": 4.5}
    return UserEntity(id=1, username=username, **(defaults | fields))


def _errors(response) -> list[tuple[str, str]]:
    return [(".".join(map(str, error["loc"][1:])), error["type"]) for error in response.json()["detail"]]


# --- POST /users ----------------------------------------------------------------------------------

def test_post_user_creates_it_in_progress_with_zero_evaluation(client, mock_session):
    response = client.post("/users", json={"username": " alice ", "email": "Alice@Example.COM", "location": MADRID})

    assert response.status_code == 201
    assert response.json() == {
        "username": "alice", "email": "Alice@example.com", "location": MADRID,
        "status": "in_progress", "evaluation": 0.0,
    }
    (entity,), _ = mock_session.add.call_args
    assert (entity.username, entity.email) == ("alice", "Alice@example.com")
    assert (entity.latitude, entity.longitude) == (40.4168, -3.7038)
    assert (entity.status, entity.evaluation) == (UserStatus.IN_PROGRESS, 0.0)
    mock_session.commit.assert_called_once()


@pytest.mark.parametrize("body", [VALID, VALID | {"location": None}], ids=["omitted", "null"])
def test_post_user_without_location(client, mock_session, body):
    response = client.post("/users", json=body)

    assert response.status_code == 201
    assert response.json()["location"] is None
    (entity,), _ = mock_session.add.call_args
    assert (entity.latitude, entity.longitude) == (None, None)


def test_post_existing_username_returns_409_without_inserting(client, mock_session):
    mock_session.scalar.return_value = _stored("alice")

    response = client.post("/users", json=VALID | {"email": "other@example.com"})

    assert response.status_code == 409
    assert response.json() == {"detail": "User 'alice' already exists."}
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


def test_post_duplicate_rejected_by_the_database_returns_409(client, mock_session):
    # The username was free when checked, but a simultaneous request inserted it first.
    mock_session.commit.side_effect = IntegrityError("INSERT", {}, UniqueViolation("duplicate key"))

    response = client.post("/users", json=VALID)

    assert response.status_code == 409
    assert response.json() == {"detail": "User 'alice' already exists."}


@pytest.mark.parametrize("body, expected_errors", [
    # username
    ({"email": "alice@example.com"}, [("username", "missing")]),
    (VALID | {"username": None}, [("username", "string_type")]),
    (VALID | {"username": "   "}, [("username", "string_too_short")]),
    (VALID | {"username": "a" * 151}, [("username", "string_too_long")]),
    # email
    ({"username": "alice"}, [("email", "missing")]),
    (VALID | {"email": None}, [("email", "string_type")]),
    (VALID | {"email": ""}, [("email", "value_error")]),
    (VALID | {"email": "not-an-email"}, [("email", "value_error")]),
    (VALID | {"email": "alice@localhost"}, [("email", "value_error")]),
    # location
    (VALID | {"location": {"latitude": 91, "longitude": 0}}, [("location.latitude", "less_than_equal")]),
    (VALID | {"location": {"latitude": 0, "longitude": -180.5}}, [("location.longitude", "greater_than_equal")]),
    (VALID | {"location": {"latitude": 10}}, [("location.longitude", "missing")]),
    (VALID | {"location": {"latitude": "10", "longitude": True}},
     [("location.latitude", "float_type"), ("location.longitude", "float_type")]),
    (VALID | {"location": MADRID | {"altitude": 650}}, [("location.altitude", "extra_forbidden")]),
    (VALID | {"location": "Madrid"}, [("location", "model_attributes_type")]),
    # fields assigned by the application
    (VALID | {"status": "active"}, [("status", "extra_forbidden")]),
    (VALID | {"evaluation": 9.5}, [("evaluation", "extra_forbidden")]),
])
def test_post_invalid_request_returns_422_without_touching_the_database(client, mock_session, body, expected_errors):
    response = client.post("/users", json=body)

    assert response.status_code == 422
    assert _errors(response) == expected_errors
    mock_session.scalar.assert_not_called()
    mock_session.add.assert_not_called()


# --- GET /users/{username} ------------------------------------------------------------------------

def test_get_user_returns_it(client, mock_session):
    mock_session.scalar.return_value = _stored("alice", latitude=40.4168, longitude=-3.7038)

    response = client.get("/users/alice")

    assert response.status_code == 200
    assert response.json() == {
        "username": "alice", "email": "alice@example.com", "location": MADRID,
        "status": "active", "evaluation": 4.5,
    }


def test_get_missing_user_returns_404(client):
    response = client.get("/users/ghost")

    assert response.status_code == 404
    assert response.json() == {"detail": "User 'ghost' not found."}
