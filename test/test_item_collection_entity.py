import pytest
from sqlalchemy import insert
from sqlalchemy.dialects import postgresql

from src.domain.enum.item_status import ItemStatus
from src.domain.model.item_collection import ItemCollection
from src.infraestructure.persistence.entities.item_collection_entity import ItemCollectionEntity
from src.infraestructure.persistence.entities.user_entity import UserEntity

BARCODE = 5050582500417


@pytest.fixture
def item(alice):
    return ItemCollection(name="Sample DVD", description="A DVD", barcode=BARCODE, owner=alice)


def _items_table(ddl: list[str]) -> str:
    return next(statement for statement in ddl if statement.startswith("CREATE TABLE item_collection "))


def test_from_domain_links_the_stored_owner_and_leaves_id_to_the_database(item, alice):
    owner = UserEntity.from_domain(alice)

    entity = ItemCollectionEntity.from_domain(item, owner)

    assert entity.id is None
    assert entity.owner is owner
    assert (entity.name, entity.description, entity.barcode) == ("Sample DVD", "A DVD", BARCODE)
    assert entity.status is ItemStatus.VALIDATING


def test_to_domain_round_trip(item, alice):
    assert ItemCollectionEntity.from_domain(item, UserEntity.from_domain(alice)).to_domain() == item


def test_postgres_schema(schema_ddl):
    ddl = schema_ddl("postgresql+psycopg://")
    create_table = _items_table(ddl)

    assert "CREATE SEQUENCE item_collection_seq" in ddl
    assert "CREATE TYPE item_status AS ENUM ('deleted', 'uploading', 'validating', 'able', 'disable')" in ddl
    assert "id BIGINT NOT NULL" in create_table
    assert "owner_id BIGINT NOT NULL" in create_table
    assert "name VARCHAR(200) NOT NULL" in create_table
    assert "description TEXT NOT NULL" in create_table
    assert "barcode BIGINT NOT NULL" in create_table
    assert "status item_status NOT NULL" in create_table
    assert ('CONSTRAINT fk_item_collection_owner_id_user FOREIGN KEY(owner_id) REFERENCES "user" (id)'
            in create_table)
    assert ("CONSTRAINT ck_item_collection_barcode_range CHECK (barcode > 0 AND barcode < 100000000000000)"
            in create_table)
    assert "CREATE INDEX ix_item_collection_owner_id ON item_collection (owner_id)" in ddl
    assert "ALTER TABLE item_collection ALTER COLUMN id SET DEFAULT nextval('item_collection_seq')" in ddl
    # The referenced table must exist first.
    assert ddl.index(create_table) > ddl.index(next(s for s in ddl if s.startswith('CREATE TABLE "user" ')))


def test_in_memory_schema(schema_ddl):
    create_table = _items_table(schema_ddl("sqlite+pysqlite://"))

    assert create_table.startswith("CREATE TABLE item_collection ( id INTEGER NOT NULL,")  # auto-increments
    assert "FOREIGN KEY(owner_id) REFERENCES user (id)" in create_table  # SQLite: no quotes needed
    assert "CHECK (barcode > 0 AND barcode < 100000000000000)" in create_table


def test_postgres_insert_takes_id_from_sequence():
    sql = str(insert(ItemCollectionEntity).values(name="x").compile(dialect=postgresql.dialect()))

    assert "nextval('item_collection_seq')" in sql


@pytest.mark.parametrize("status", list(ItemStatus))
def test_status_is_stored_by_value_not_by_name(status):
    assert status.value in ItemCollectionEntity.__table__.c.status.type.enums
