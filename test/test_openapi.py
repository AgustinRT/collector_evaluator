import json
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app, export_openapi, parse_startup_args
from src.infraestructure.api_router.openapi import API_VERSION, openapi_json
from src.domain.model.item_collection import ItemCollection
from src.infraestructure.bootstrap.dependencies import get_db_session
from src.infraestructure.persistence.entities.item_collection_entity import ItemCollectionEntity
from src.infraestructure.persistence.entities.user_entity import UserEntity

ROOT = Path(__file__).resolve().parent.parent
COMMITTED_SPEC = ROOT / "docs" / "openapi.json"
SPEC = app.openapi()
OPERATIONS = [(path, method, operation) for path, methods in SPEC["paths"].items() for method, operation in methods.items()]


def _documented_examples(path: str) -> list[tuple[str, dict]]:
    examples = SPEC["paths"][path]["post"]["requestBody"]["content"]["application/json"]["examples"]
    return [(name, example["value"]) for name, example in examples.items()]


@pytest.fixture
def client(mock_session, alice):
    app.dependency_overrides[get_db_session] = lambda: mock_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_committed_spec_is_up_to_date():
    assert COMMITTED_SPEC.read_text(encoding="utf-8") == openapi_json(app), (
        "docs/openapi.json is outdated. Regenerate it with: python main.py --export-openapi docs/openapi.json")


def test_api_version_matches_pyproject():
    with (ROOT / "pyproject.toml").open("rb") as pyproject:
        assert API_VERSION == tomllib.load(pyproject)["project"]["version"]


def test_docs_are_served(client):
    assert client.get("/openapi.json").json() == SPEC
    for page, marker in (("/docs", "swagger-ui"), ("/redoc", "redoc")):
        response = client.get(page)
        assert response.status_code == 200
        assert marker in response.text
        assert "/openapi.json" in response.text


@pytest.mark.parametrize("path, method, operation", OPERATIONS, ids=[f"{m.upper()} {p}" for p, m, _ in OPERATIONS])
def test_every_operation_is_documented(path, method, operation):
    assert operation.get("summary")
    assert operation.get("tags")
    if path != "/":
        assert operation.get("description")
    for code, response in operation["responses"].items():
        if code.startswith("4") and code != "422":
            assert response["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
            assert response["content"]["application/json"]["example"]["detail"]


@pytest.mark.parametrize("name, body", _documented_examples("/users"))
def test_documented_user_examples_are_accepted(client, mock_session, name, body):
    mock_session.scalar.return_value = None  # username is free

    response = client.post("/users", json=body)

    assert response.status_code == 201, response.json()


@pytest.mark.parametrize("name, body", _documented_examples("/users/{username}/items"))
def test_documented_item_examples_are_accepted(client, mock_session, database_assigns_ids, alice, name, body):
    mock_session.scalar.return_value = UserEntity.from_domain(alice)  # the owner exists

    response = client.post("/users/alice/items", json=body)

    assert response.status_code == 201, response.json()


@pytest.mark.parametrize("name, body", _documented_examples("/users/{username}/collections"))
def test_documented_collection_examples_are_accepted(client, database_assigns_ids, alice, name, body):
    owner = UserEntity.from_domain(alice.model_copy(update={"status": "in_progress"}))
    items = [ItemCollectionEntity.from_domain(
        ItemCollection(name="DVD", description="d", barcode=5050582500417, owner=alice), owner) for _ in body["item_ids"]]
    for item, item_id in zip(items, body["item_ids"]):
        item.id = item_id
    database_assigns_ids.scalar.return_value = owner
    database_assigns_ids.scalars.return_value = items  # the user owns exactly the documented items

    response = client.post("/users/alice/collections", json=body)

    assert response.status_code == 201, response.json()


def test_export_openapi_writes_the_spec(tmp_path):
    target = tmp_path / "docs" / "openapi.json"

    export_openapi(target)

    assert json.loads(target.read_text(encoding="utf-8")) == SPEC


def test_export_openapi_cli_flag():
    assert parse_startup_args(["--export-openapi", "docs/openapi.json"]).export_openapi == Path("docs/openapi.json")
    assert parse_startup_args([]).export_openapi is None
