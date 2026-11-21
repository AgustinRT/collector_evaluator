-- =====================================================================================================================
-- Initializes the collector_evaluator database: creates it if it does not exist, then applies its schema.
--
-- Usage (psql, from the repository root):
--     psql -h localhost -U postgres -f database/init.sql
--
-- Safe to run more than once: existing objects are kept. Requires PostgreSQL 14 or later.
-- =====================================================================================================================

\set ON_ERROR_STOP on

-- CREATE DATABASE has no IF NOT EXISTS: \gexec only runs it when the database is missing.
-- UTF8 is set explicitly because the application does not work with SQL_ASCII databases.
SELECT 'CREATE DATABASE collector_evaluator ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'collector_evaluator')
\gexec

\connect collector_evaluator

\ir schema/schema.sql
