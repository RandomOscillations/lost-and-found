-- Base bootstrap for local/dev databases.
-- Apply manually or via `psql -f infra/sql/000_init.sql postgres://...` before running services.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- Core schemas (services own tables within these namespaces).
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS items;
CREATE SCHEMA IF NOT EXISTS claims;

-- The ORM models target these schemas by setting search_path per connection.
-- When running in Docker, the services automatically call `Base.metadata.create_all`
-- on startup, so this file only needs to be applied when bootstrapping a fresh
-- Postgres instance outside of docker-compose.
