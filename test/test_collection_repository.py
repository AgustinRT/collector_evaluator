import pytest
from sqlalchemy.dialects import postgresql

from src.domain.exception.item_exception import ItemsNotFoundError
from src.domain.exception.user_exception import UserNotFoundError
from src.domain.model.collection import Collection
from src.domain.model.item_collection import ItemCollection
from src.infraestructure.persistence.entities.collection_entity import CollectionEntity
from src.infraestructure.persistence.entities.item_collection_entity import ItemCollectionEntity
from src.infraestructure.persistence.entities.user_entity import UserEntity
from src.infraestructure.persistence.repositories.collection_repository import SqlAlchemyCollectionRepository


@pytest.fixture
def stored_owner(alice):
    entity = UserEntity.from_domain(alice)
    entity.id = 1
    return entity


@pytest.fixture
def stored_items(alice, stored_owner):
    entities = []
    for item_id in (1, 2):
        entity = ItemCollectionEntity.from_domain(
            ItemCollection(name=f"Item {item_id}", description="d", barcode=5050582500417, owner=alice), stored_owner)
        entity.id = item_id
        entities.append(entity)
    return entities


@pytest.fixture
def collection(alice, stored_items):
    return Collection(name="Films", description="d", owner=alice, items=[item.to_domain() for item in stored_items])


def _sql(statement) -> str:
    return " ".join(str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).split())


def test_create_collection_links_owner_and_items_and_returns_its_id(
        database_assigns_ids, stored_owner, stored_items, collection):
    session = database_assigns_ids
    session.scalar.return_value = stored_owner
    session.scalars.return_value = stored_items

    created = SqlAlchemyCollectionRepository(session).create_collection(collection)

    (items_query,), _ = session.scalars.call_args
    sql = _sql(items_query)
    assert "item_collection.id IN (1, 2)" in sql
    assert "item_collection.owner_id = 1" in sql  # never another user's items
    (entity,), _ = session.add.call_args
    assert isinstance(entity, CollectionEntity)
    assert entity.owner is stored_owner
    assert entity.items == stored_items
    session.commit.assert_called_once()
    assert created.id == 1
    assert [item.id for item in created.items] == [1, 2]


def test_create_collection_for_owner_not_stored(mock_session, collection):
    mock_session.scalar.return_value = None

    with pytest.raises(UserNotFoundError):
        SqlAlchemyCollectionRepository(mock_session).create_collection(collection)

    mock_session.add.assert_not_called()


def test_create_collection_with_items_not_stored_for_the_owner(mock_session, stored_owner, stored_items, collection):
    mock_session.scalar.return_value = stored_owner
    mock_session.scalars.return_value = stored_items[:1]

    with pytest.raises(ItemsNotFoundError) as exc_info:
        SqlAlchemyCollectionRepository(mock_session).create_collection(collection)

    assert exc_info.value.item_ids == [2]
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


def test_list_collections_by_owner(mock_session, stored_owner, stored_items):
    mock_session.scalars.return_value = [
        CollectionEntity(id=1, name="Films", description="d", owner=stored_owner, items=stored_items)]

    collections = SqlAlchemyCollectionRepository(mock_session).list_collections_by_owner("alice")

    assert [(c.id, [i.id for i in c.items]) for c in collections] == [(1, [1, 2])]
    (statement,), _ = mock_session.scalars.call_args
    sql = _sql(statement)
    assert sql.startswith('SELECT "user".id')  # the owner comes from the same query
    assert 'FROM collection JOIN "user" ON "user".id = collection.owner_id' in sql
    assert """WHERE "user".username = 'alice'""" in sql
    assert "ORDER BY collection.id" in sql


def test_list_collections_by_item(mock_session, stored_owner, stored_items):
    mock_session.scalars.return_value = [
        CollectionEntity(id=1, name="Films", description="d", owner=stored_owner, items=stored_items)]

    collections = SqlAlchemyCollectionRepository(mock_session).list_collections_by_item(2)

    assert [c.id for c in collections] == [1]
    (statement,), _ = mock_session.scalars.call_args
    sql = _sql(statement)
    assert "JOIN collection_item ON collection_item.collection_id = collection.id" in sql
    assert 'LEFT OUTER JOIN "user" AS user_1 ON user_1.id = collection.owner_id' in sql  # owner in the same query
    assert "WHERE collection_item.item_id = 2" in sql
    assert "ORDER BY collection.id" in sql


@pytest.mark.parametrize("method, argument", [("list_collections_by_owner", "alice"), ("list_collections_by_item", 1)])
def test_list_without_collections(mock_session, method, argument):
    mock_session.scalars.return_value = []

    assert getattr(SqlAlchemyCollectionRepository(mock_session), method)(argument) == []
