import pytest
from sqlalchemy.dialects import postgresql

from src.domain.exception.user_exception import UserNotFoundError
from src.domain.model.item_collection import ItemCollection
from src.infraestructure.persistence.entities.item_collection_entity import ItemCollectionEntity
from src.infraestructure.persistence.entities.user_entity import UserEntity
from src.infraestructure.persistence.repositories.item_collection_repository import SqlAlchemyItemCollectionRepository

BARCODE = 5050582500417


@pytest.fixture
def stored_alice(alice):
    entity = UserEntity.from_domain(alice)
    entity.id = 1
    return entity


@pytest.fixture
def item(alice):
    return ItemCollection(name="Sample DVD", description="A DVD", barcode=BARCODE, owner=alice)


def _sql(statement) -> str:
    return " ".join(str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).split())


def test_create_item_links_it_to_the_stored_owner_and_commits(mock_session, stored_alice, item):
    mock_session.scalar.return_value = stored_alice

    created = SqlAlchemyItemCollectionRepository(mock_session).create_item(item)

    (owner_query,), _ = mock_session.scalar.call_args
    assert """FROM "user" WHERE "user".username = 'alice'""" in _sql(owner_query)
    (entity,), _ = mock_session.add.call_args
    assert isinstance(entity, ItemCollectionEntity)
    assert entity.id is None
    assert entity.owner is stored_alice
    mock_session.commit.assert_called_once()
    assert created == item


def test_create_item_for_owner_not_stored_fails_without_inserting(mock_session, item):
    mock_session.scalar.return_value = None

    with pytest.raises(UserNotFoundError):
        SqlAlchemyItemCollectionRepository(mock_session).create_item(item)

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


def test_list_items_by_owner_loads_items_and_owner_in_one_query(mock_session, stored_alice, item):
    entities = [ItemCollectionEntity.from_domain(item.model_copy(update={"name": f"Item {n}"}), stored_alice)
                for n in range(3)]
    mock_session.scalars.return_value = entities

    items = SqlAlchemyItemCollectionRepository(mock_session).list_items_by_owner("alice")

    assert [listed.name for listed in items] == ["Item 0", "Item 1", "Item 2"]
    assert all(listed.owner.username == "alice" for listed in items)
    (statement,), _ = mock_session.scalars.call_args
    sql = _sql(statement)
    assert 'FROM item_collection JOIN "user" ON "user".id = item_collection.owner_id' in sql
    assert """WHERE "user".username = 'alice'""" in sql
    assert "ORDER BY item_collection.id" in sql
    assert sql.startswith('SELECT "user".id, "user".username')  # owner columns come from the same query


def test_list_items_by_owner_without_items(mock_session):
    mock_session.scalars.return_value = []

    assert SqlAlchemyItemCollectionRepository(mock_session).list_items_by_owner("alice") == []


def test_get_items_only_returns_the_owner_items_with_those_ids(mock_session, stored_alice, item):
    entity = ItemCollectionEntity.from_domain(item, stored_alice)
    entity.id = 3
    mock_session.scalars.return_value = [entity]

    items = SqlAlchemyItemCollectionRepository(mock_session).get_items("alice", [3, 4])

    assert [(found.id, found.owner.username) for found in items] == [(3, "alice")]
    (statement,), _ = mock_session.scalars.call_args
    sql = _sql(statement)
    assert """WHERE "user".username = 'alice' AND item_collection.id IN (3, 4)""" in sql
    assert "ORDER BY item_collection.id" in sql
