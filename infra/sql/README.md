# SQL Bootstrap

Use the scripts in this directory to seed a brand new Postgres instance before the
services run. They are intentionally service-agnostic and can be executed against any
environment (local, staging, prod) to ensure required extensions exist.

```bash
psql "$DATABASE_URL" -f infra/sql/000_init.sql
```

The individual services still manage their own tables via SQLAlchemy metadata or
Alembic migrations. Keeping the extension/namespace bootstrap scripts here makes it
easy to run them in CI/CD or during the first deploy to a managed Postgres cluster.
