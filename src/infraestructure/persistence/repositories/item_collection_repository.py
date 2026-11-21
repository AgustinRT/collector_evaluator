

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager

from src.application.ports.outbound.item_collection_port_out import ItemCollectionPortOut
from src.domain.exception.user_exception import UserNotFoundError
from src.domain.model.item_collection import ItemCollection
from src.infraestructure.persistence.entities.item_collection_entity import ItemCollectionEntity
from src.infraestructure.persistence.entities.user_entity import UserEntity


class SqlAlchemyItemCollectionRepository(ItemCollectionPortOut):
    """
    Persistence adapter for the item outbound port, using SQLAlchemy (psycopg driver on PostgreSQL).
    """

    def __init__(self, session: Session):
        self._session = session

    def create_item(self, item: ItemCollection) -> ItemCollection:
        owner = self._session.scalar(select(UserEntity).where(UserEntity.username == item.owner.username))
        if owner is None:
            raise UserNotFoundError(item.owner.username)
        entity = ItemCollectionEntity.from_domain(item, owner)
        self._session.add(entity)
        # Each creation is its own unit of work (see SqlAlchemyUserRepository.create_user).
        self._session.commit()
        return entity.to_domain()

    def get_items(self, owner_username: str, item_ids: Iterable[int]) -> list[ItemCollection]:
        statement = (
            select(ItemCollectionEntity)
            .join(ItemCollectionEntity.owner)
            .where(UserEntity.username == owner_username, ItemCollectionEntity.id.in_(list(item_ids)))
            .options(contains_eager(ItemCollectionEntity.owner))
            .order_by(ItemCollectionEntity.id)
        )
        return [entity.to_domain() for entity in self._session.scalars(statement)]

    def list_items_by_owner(self, owner_username: str) -> list[ItemCollection]:
        statement = (
            select(ItemCollectionEntity)
            .join(ItemCollectionEntity.owner)
            .where(UserEntity.username == owner_username)
            # Fill each item's owner from the join above instead of one extra query per item.
            .options(contains_eager(ItemCollectionEntity.owner))
            .order_by(ItemCollectionEntity.id)
        )
        return [entity.to_domain() for entity in self._session.scalars(statement)]
