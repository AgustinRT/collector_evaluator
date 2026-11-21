import pytest
from sqlalchemy import insert, inspect
from sqlalchemy.dialects import postgresql

from src.domain.model.collection import Collection
from src.domain.model.item_collection import ItemCollection
from src.infraestructure.persistence.entities.collection_entity import CollectionEntity
from src.infraestructure.persistence.entities.item_collection_entity import ItemCollectionEntity
from src.infraestructure.persistence.entities.user_entity import UserEntity


@pytest.fixture
def stored_owner(alice):
    return UserEntity.from_domain(alice)


@pytest.fixture
def stored_items(alice, stored_owner):
    entities = []
    for item_id in (1, 2):
        entity = ItemCollectionEntity.from_domain(
            ItemCollection(name=f"Item {item_id}", description="d", barcode=5050582500417, owner=alice), stored_owner)
        entity.id = item_id
        entities.append(entity)
    return entities


def _statement(ddl: list[str], prefix: str) -> str:
    return next(statement for statement in ddl if statement.startswith(prefix))


def test_from_domain_links_owner_and_items_and_leaves_id_to_the_database(alice, stored_owner, stored_items):
    collection = Collection(name="Films", description="d", owner=alice, items=[i.to_domain() for i in stored_items])

    entity = CollectionEntity.from_domain(collection, stored_owner, stored_items)

    assert entity.id is None
    assert entity.owner is stored_owner
    assert entity.items == stored_items
    assert (entity.name, entity.description) == ("Films", "d")


def test_to_domain(stored_owner, stored_items):
    entity = CollectionEntity(id=5, name="Films", description="d", owner=stored_owner, items=stored_items)

    collection = entity.to_domain()

    assert (collection.id, collection.name, collection.owner.username) == (5, "Films", "alice")
    assert [item.id for item in collection.items] == [1, 2]


def test_postgres_schema(schema_ddl):
    ddl = schema_ddl("postgresql+psycopg://")
    collections = _statement(ddl, "CREATE TABLE collection ")
    links = _statement(ddl, "CREATE TABLE collection_item ")

    assert "CREATE SEQUENCE collection_seq" in ddl
    assert "ALTER TABLE collection ALTER COLUMN id SET DEFAULT nextval('collection_seq')" in ddl
    for column in ("id BIGINT NOT NULL", "owner_id BIGINT NOT NULL", "name VARCHAR(200) NOT NULL",
                   "description TEXT NOT NULL"):
        assert column in collections
    assert 'CONSTRAINT fk_collection_owner_id_user FOREIGN KEY(owner_id) REFERENCES "user" (id)' in collections
    assert "CREATE INDEX ix_collection_owner_id ON collection (owner_id)" in ddl
    # The link table: one row per (collection, item), so an item cannot be twice in a collection.
    assert "PRIMARY KEY (collection_id, item_id)" in links
    assert ("FOREIGN KEY(collection_id) REFERENCES collection (id) ON DELETE CASCADE" in links)
    assert "FOREIGN KEY(item_id) REFERENCES item_collection (id)" in links
    assert "FOREIGN KEY(item_id) REFERENCES item_collection (id) ON DELETE" not in links  # collected items are kept
    assert "CREATE INDEX ix_collection_item_item_id ON collection_item (item_id)" in ddl
    # Referenced tables are created first.
    assert ddl.index(links) > max(ddl.index(collections), ddl.index(_statement(ddl, "CREATE TABLE item_collection ")))


def test_in_memory_schema(schema_ddl):
    ddl = schema_ddl("sqlite+pysqlite://")

    assert _statement(ddl, "CREATE TABLE collection ").startswith("CREATE TABLE collection ( id INTEGER NOT NULL,")
    assert "PRIMARY KEY (collection_id, item_id)" in _statement(ddl, "CREATE TABLE collection_item ")


def test_items_are_loaded_in_one_batch_for_all_collections():
    # Without it, listing N collections would run one extra query per collection.
    assert inspect(CollectionEntity).relationships["items"].lazy == "selectin"


def test_postgres_insert_takes_id_from_sequence():
    sql = str(insert(CollectionEntity).values(name="x").compile(dialect=postgresql.dialect()))

    assert "nextval('collection_seq')" in sql
