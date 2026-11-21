

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.application.ports.inbound.collection_port_in import CollectionPortIn
from src.application.ports.inbound.item_collection_port_in import ItemCollectionPortIn
from src.application.ports.inbound.user_port_in import UserPortIn
from src.application.ports.outbound.collection_port_out import CollectionPortOut
from src.application.ports.outbound.item_collection_port_out import ItemCollectionPortOut
from src.application.ports.outbound.user_port_out import UserPortOut
from src.application.use_cases.collection_service import CollectionService
from src.application.use_cases.item_collection_service import ItemCollectionService
from src.application.use_cases.user_service import UserService
from src.infraestructure.persistence.repositories.collection_repository import SqlAlchemyCollectionRepository
from src.infraestructure.persistence.repositories.item_collection_repository import SqlAlchemyItemCollectionRepository
from src.infraestructure.persistence.repositories.user_repository import SqlAlchemyUserRepository

# Composition root: the only place where ports are bound to concrete adapters.
# Tests (or alternative deployments) swap implementations via app.dependency_overrides.


def get_db_session(request: Request) -> Iterator[Session]:
    """
    Opens one session per request from the factory created at startup (see lifespan) and closes it
    afterwards. Uncommitted work is rolled back.
    """
    with request.app.state.session_factory() as session:
        yield session


def get_user_repository(session: Annotated[Session, Depends(get_db_session)]) -> UserPortOut:
    return SqlAlchemyUserRepository(session)


def get_user_service(user_repository: Annotated[UserPortOut, Depends(get_user_repository)]) -> UserPortIn:
    return UserService(user_repository)


def get_item_collection_repository(session: Annotated[Session, Depends(get_db_session)]) -> ItemCollectionPortOut:
    return SqlAlchemyItemCollectionRepository(session)


def get_item_collection_service(
    item_repository: Annotated[ItemCollectionPortOut, Depends(get_item_collection_repository)],
    user_repository: Annotated[UserPortOut, Depends(get_user_repository)],
) -> ItemCollectionPortIn:
    # FastAPI resolves get_db_session once per request, so both repositories share one session.
    return ItemCollectionService(item_repository, user_repository)


def get_collection_repository(session: Annotated[Session, Depends(get_db_session)]) -> CollectionPortOut:
    return SqlAlchemyCollectionRepository(session)


def get_collection_service(
    collection_repository: Annotated[CollectionPortOut, Depends(get_collection_repository)],
    item_repository: Annotated[ItemCollectionPortOut, Depends(get_item_collection_repository)],
    user_repository: Annotated[UserPortOut, Depends(get_user_repository)],
) -> CollectionPortIn:
    return CollectionService(collection_repository, item_repository, user_repository)
