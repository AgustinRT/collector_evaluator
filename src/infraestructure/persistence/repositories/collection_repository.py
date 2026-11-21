

from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager, joinedload

from src.application.ports.outbound.collection_port_out import CollectionPortOut
from src.domain.exception.item_exception import ItemsNotFoundError
from src.domain.exception.user_exception import UserNotFoundError
from src.domain.model.collection import Collection
from src.infraestructure.persistence.entities.collection_entity import CollectionEntity, collection_items
from src.infraestructure.persistence.entities.item_collection_entity import ItemCollectionEntity
from src.infraestructure.persistence.entities.user_entity import UserEntity


class SqlAlchemyCollectionRepository(CollectionPortOut):
    """
    Persistence adapter for the collection outbound port, using SQLAlchemy (psycopg driver on PostgreSQL).
    """

    def __init__(self, session: Session):
        self._session = session

    def create_collection(self, collection: Collection) -> Collection:
        owner = self._session.scalar(select(UserEntity).where(UserEntity.username == collection.owner.username))
        if owner is None:
            raise UserNotFoundError(collection.owner.username)
        item_ids = [item.id for item in collection.items]
        # Filtering by owner too guarantees a collection never links another user's items.
        items = list(self._session.scalars(
            select(ItemCollectionEntity)
            .where(ItemCollectionEntity.id.in_(item_ids), ItemCollectionEntity.owner_id == owner.id)
            .order_by(ItemCollectionEntity.id)
        ))
        missing = set(item_ids) - {item.id for item in items}
        if missing:
            raise ItemsNotFoundError(owner.username, missing)
        entity = CollectionEntity.from_domain(collection, owner, items)
        self._session.add(entity)
        # Each creation is its own unit of work (see SqlAlchemyUserRepository.create_user).
        self._session.commit()
        return entity.to_domain()

    def list_collections_by_owner(self, owner_username: str) -> list[Collection]:
        statement = (
            select(CollectionEntity)
            .join(CollectionEntity.owner)
            .where(UserEntity.username == owner_username)
            .options(contains_eager(CollectionEntity.owner))
            .order_by(CollectionEntity.id)
        )
        return [entity.to_domain() for entity in self._session.scalars(statement)]

    def list_collections_by_item(self, item_id: int) -> list[Collection]:
        statement = (
            select(CollectionEntity)
            .join(collection_items, collection_items.c.collection_id == CollectionEntity.id)
            .where(collection_items.c.item_id == item_id)
            .options(joinedload(CollectionEntity.owner))
            .order_by(CollectionEntity.id)
        )
        return [entity.to_domain() for entity in self._session.scalars(statement)]
