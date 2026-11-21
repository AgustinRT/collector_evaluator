from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from main import app
from src.application.use_cases.collection_service import CollectionService
from src.application.use_cases.item_collection_service import ItemCollectionService
from src.application.use_cases.user_service import UserService
from src.infraestructure.bootstrap import dependencies
from src.infraestructure.persistence.entities.user_entity import UserEntity
from src.infraestructure.persistence.repositories.collection_repository import SqlAlchemyCollectionRepository
from src.infraestructure.persistence.repositories.item_collection_repository import SqlAlchemyItemCollectionRepository
from src.infraestructure.persistence.repositories.user_repository import SqlAlchemyUserRepository


def test_get_db_session_uses_the_factory_from_app_state_and_closes_the_session(mock_session):
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = mock_session
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(session_factory=session_factory)))

    provider = dependencies.get_db_session(request)
    assert next(provider) is mock_session
    session_factory.return_value.__exit__.assert_not_called()

    provider.close()
    session_factory.return_value.__exit__.assert_called_once()


def test_providers_bind_ports_to_adapters(mock_session):
    repository = dependencies.get_user_repository(mock_session)
    service = dependencies.get_user_service(repository)

    assert isinstance(repository, SqlAlchemyUserRepository)
    assert isinstance(service, UserService)


def test_item_providers_bind_ports_to_adapters(mock_session):
    item_repository = dependencies.get_item_collection_repository(mock_session)
    service = dependencies.get_item_collection_service(item_repository, dependencies.get_user_repository(mock_session))

    assert isinstance(item_repository, SqlAlchemyItemCollectionRepository)
    assert isinstance(service, ItemCollectionService)


def test_collection_providers_bind_ports_to_adapters(mock_session):
    collection_repository = dependencies.get_collection_repository(mock_session)
    service = dependencies.get_collection_service(
        collection_repository,
        dependencies.get_item_collection_repository(mock_session),
        dependencies.get_user_repository(mock_session),
    )

    assert isinstance(collection_repository, SqlAlchemyCollectionRepository)
    assert isinstance(service, CollectionService)


def test_item_and_user_repositories_share_one_session_per_request(mock_session, database_assigns_ids, alice):
    opened = []

    def counting_session():
        opened.append(mock_session)
        yield mock_session

    mock_session.scalar.return_value = UserEntity.from_domain(alice)
    app.dependency_overrides[dependencies.get_db_session] = counting_session
    try:
        response = TestClient(app).post(
            "/users/alice/items", json={"name": "DVD", "description": "d", "barcode": 5050582500417})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert len(opened) == 1
