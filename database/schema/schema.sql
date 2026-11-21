-- =====================================================================================================================
-- Schema of the collector_evaluator database.
--
-- Applied by database/init.sql, and by the application at startup on PostgreSQL, so it must stay idempotent:
-- every object is created only if it does not exist yet. It never alters or drops existing objects.
-- Requires PostgreSQL 14 or later (CREATE OR REPLACE TRIGGER).
--
-- Table and column names must match the SQLAlchemy entities in src/infraestructure/persistence/entities/
-- (checked by test/test_database_script.py).
-- =====================================================================================================================

BEGIN;

-- Serializes concurrent runs (e.g. several application instances starting at the same time).
SELECT pg_advisory_xact_lock(hashtext('collector_evaluator.schema'));


-- ---------------------------------------------------------------------------------------------------------------------
-- Enums (values must match src/domain/enum/*.py)
-- ---------------------------------------------------------------------------------------------------------------------

DO $$ BEGIN
    CREATE TYPE user_status AS ENUM ('deleted', 'in_progress', 'active', 'inactive', 'blocked');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE item_status AS ENUM ('deleted', 'uploading', 'validating', 'able', 'disable');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE history_operation AS ENUM ('INSERT', 'UPDATE', 'DELETE');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ---------------------------------------------------------------------------------------------------------------------
-- Sequences: ids are always assigned by the database, never by the application.
-- ---------------------------------------------------------------------------------------------------------------------

CREATE SEQUENCE IF NOT EXISTS user_seq;
CREATE SEQUENCE IF NOT EXISTS item_collection_seq;
CREATE SEQUENCE IF NOT EXISTS collection_seq;


-- ---------------------------------------------------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------------------------------------------------

-- "user" is a reserved word in PostgreSQL, so it must always be written in double quotes.
CREATE TABLE IF NOT EXISTS "user" (
    id          bigint           NOT NULL DEFAULT nextval('user_seq'),
    username    varchar(150)     NOT NULL,
    email       varchar(254)     NOT NULL,
    latitude    double precision,
    longitude   double precision,
    status      user_status      NOT NULL,
    evaluation  double precision NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_user_username UNIQUE (username),
    CONSTRAINT ck_user_location_complete CHECK ((latitude IS NULL) = (longitude IS NULL)),
    CONSTRAINT ck_user_latitude_range CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT ck_user_longitude_range CHECK (longitude BETWEEN -180 AND 180)
);
ALTER SEQUENCE user_seq OWNED BY "user".id;
COMMENT ON TABLE "user" IS 'Registered users (src/domain/model/user.py).';

CREATE TABLE IF NOT EXISTS item_collection (
    id          bigint       NOT NULL DEFAULT nextval('item_collection_seq'),
    owner_id    bigint       NOT NULL,
    name        varchar(200) NOT NULL,
    description text         NOT NULL,
    barcode     bigint       NOT NULL,
    status      item_status  NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_item_collection_barcode_range CHECK (barcode > 0 AND barcode < 100000000000000),
    CONSTRAINT fk_item_collection_owner_id_user FOREIGN KEY (owner_id) REFERENCES "user" (id)
);
ALTER SEQUENCE item_collection_seq OWNED BY item_collection.id;
CREATE INDEX IF NOT EXISTS ix_item_collection_owner_id ON item_collection (owner_id);
COMMENT ON TABLE item_collection IS 'Collectible items, each owned by a user (src/domain/model/item_collection.py).';

CREATE TABLE IF NOT EXISTS collection (
    id          bigint       NOT NULL DEFAULT nextval('collection_seq'),
    owner_id    bigint       NOT NULL,
    name        varchar(200) NOT NULL,
    description text         NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_collection_owner_id_user FOREIGN KEY (owner_id) REFERENCES "user" (id)
);
ALTER SEQUENCE collection_seq OWNED BY collection.id;
CREATE INDEX IF NOT EXISTS ix_collection_owner_id ON collection (owner_id);
COMMENT ON TABLE collection IS 'Named groups of items of a user (src/domain/model/collection.py). Names are not unique.';

-- The items of each collection (Collection.items): many-to-many, an item can be in several collections.
CREATE TABLE IF NOT EXISTS collection_item (
    collection_id bigint NOT NULL,
    item_id       bigint NOT NULL,
    PRIMARY KEY (collection_id, item_id),
    CONSTRAINT fk_collection_item_collection_id_collection
        FOREIGN KEY (collection_id) REFERENCES collection (id) ON DELETE CASCADE,
    CONSTRAINT fk_collection_item_item_id_item_collection
        FOREIGN KEY (item_id) REFERENCES item_collection (id)
);
CREATE INDEX IF NOT EXISTS ix_collection_item_item_id ON collection_item (item_id);
COMMENT ON TABLE collection_item IS 'Items of each collection.';


-- ---------------------------------------------------------------------------------------------------------------------
-- History
--
-- Every table T has a T_history table with:
--   * history_id: order of the changes.
--   * operation:  INSERT, UPDATE or DELETE.
--   * changed_at: time of the transaction that made the change.
--   * changed_by: database role that made the change.
--   * a copy of every column of T: the row after the change (before it, for DELETE).
-- History tables have no constraints on the copied columns, so they never block a change to T and keep the
-- rows of deleted records.
-- ---------------------------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS user_history (
    history_id  bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    operation   history_operation NOT NULL,
    changed_at  timestamptz       NOT NULL,
    changed_by  text              NOT NULL,
    id          bigint,
    username    varchar(150),
    email       varchar(254),
    latitude    double precision,
    longitude   double precision,
    status      user_status,
    evaluation  double precision
);
CREATE INDEX IF NOT EXISTS ix_user_history_id ON user_history (id);
COMMENT ON TABLE user_history IS 'Every change made to "user".';

CREATE TABLE IF NOT EXISTS item_collection_history (
    history_id  bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    operation   history_operation NOT NULL,
    changed_at  timestamptz       NOT NULL,
    changed_by  text              NOT NULL,
    id          bigint,
    owner_id    bigint,
    name        varchar(200),
    description text,
    barcode     bigint,
    status      item_status
);
CREATE INDEX IF NOT EXISTS ix_item_collection_history_id ON item_collection_history (id);
COMMENT ON TABLE item_collection_history IS 'Every change made to item_collection.';

CREATE TABLE IF NOT EXISTS collection_history (
    history_id  bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    operation   history_operation NOT NULL,
    changed_at  timestamptz       NOT NULL,
    changed_by  text              NOT NULL,
    id          bigint,
    owner_id    bigint,
    name        varchar(200),
    description text
);
CREATE INDEX IF NOT EXISTS ix_collection_history_id ON collection_history (id);
COMMENT ON TABLE collection_history IS 'Every change made to collection.';

CREATE TABLE IF NOT EXISTS collection_item_history (
    history_id    bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    operation     history_operation NOT NULL,
    changed_at    timestamptz       NOT NULL,
    changed_by    text              NOT NULL,
    collection_id bigint,
    item_id       bigint
);
CREATE INDEX IF NOT EXISTS ix_collection_item_history_collection_id ON collection_item_history (collection_id);
COMMENT ON TABLE collection_item_history IS 'Every item added to or removed from a collection.';

-- Generic trigger function: copies the changed row into <table>_history. Columns are matched by name (through
-- jsonb), so the column order of both tables does not matter. Updates that change nothing are not recorded.
CREATE OR REPLACE FUNCTION record_history() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    history_table text := format('%I.%I', TG_TABLE_SCHEMA, TG_TABLE_NAME || '_history');
BEGIN
    IF TG_OP = 'UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN
        RETURN NULL;
    END IF;
    EXECUTE format('INSERT INTO %s SELECT * FROM jsonb_populate_record(NULL::%s, $1)', history_table, history_table)
    USING to_jsonb(CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END) || jsonb_build_object(
        'history_id', nextval(pg_get_serial_sequence(history_table, 'history_id')),
        'operation', TG_OP,
        'changed_at', now(),
        'changed_by', current_user
    );
    RETURN NULL;
END
$$;

CREATE OR REPLACE TRIGGER user_history
    AFTER INSERT OR UPDATE OR DELETE ON "user"
    FOR EACH ROW EXECUTE FUNCTION record_history();

CREATE OR REPLACE TRIGGER item_collection_history
    AFTER INSERT OR UPDATE OR DELETE ON item_collection
    FOR EACH ROW EXECUTE FUNCTION record_history();

CREATE OR REPLACE TRIGGER collection_history
    AFTER INSERT OR UPDATE OR DELETE ON collection
    FOR EACH ROW EXECUTE FUNCTION record_history();

CREATE OR REPLACE TRIGGER collection_item_history
    AFTER INSERT OR UPDATE OR DELETE ON collection_item
    FOR EACH ROW EXECUTE FUNCTION record_history();

COMMIT;
