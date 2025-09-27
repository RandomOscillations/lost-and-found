# Runbooks

## Local development

1. **Generate JWT keys (first time only)**
   ```bash
   mkdir -p infra/keys
   openssl genrsa -out infra/keys/jwt.key 2048
   openssl rsa -in infra/keys/jwt.key -pubout -out infra/keys/jwt.pub
   ```
2. **Start the stack**
   ```bash
   ./scripts/dev.up.sh
   ```
   This builds and starts Postgres, Redis, NATS, MinIO, Mailpit, and the four FastAPI services.
3. **Verify health**
   ```bash
   curl http://127.0.0.1:8000/healthz
   ./scripts/e2e.sh
   ```
4. **Shut down**
   ```bash
   ./scripts/dev.down.sh
   ```

### Running a single service manually

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/lostfound
export JWT_PRIVATE_KEY_PATH=$(pwd)/infra/keys/jwt.key
export JWT_PUBLIC_KEY_PATH=$(pwd)/infra/keys/jwt.pub
export NATS_URL=nats://127.0.0.1:4222
uvicorn services.auth_service.app:app --reload --port 8001
```

Swap the entry point and port for intake (`services.intake_service.app:app`/8002), vision (`services.vision_service.app:app`/8003), or gateway (`lostfound.main:app`/8000). The gateway additionally needs `AUTH_SERVICE_URL`, `INTAKE_SERVICE_URL`, and `VISION_SERVICE_URL` pointing at the running services.

## Database bootstrap & migrations

- Bootstrap extensions/schemas once per database:
  ```bash
  psql "$DATABASE_URL" -f infra/sql/000_init.sql
  ```
- Today the services call `Base.metadata.create_all()` on startup for simple MVP tables. When we move to Alembic per service, place migration scripts under `infra/sql` (or service-specific `alembic/`) and reference them here.
- If something goes sideways locally, `docker compose down -v` from the `infra/` folder wipes the Postgres volume so you can start clean.

## First deployment checklist

1. Provision managed services: Postgres (with pgvector), Redis, NATS, object storage (S3/MinIO-compatible), SMTP relay.
2. Run `infra/sql/000_init.sql` against the new Postgres instance.
3. Generate and store the RSA key pair in your secret manager (`JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH`).
4. Build and push images:
   ```bash
   docker build -f docker/Dockerfile.auth -t <registry>/auth:latest .
   docker build -f docker/Dockerfile.intake -t <registry>/intake:latest .
   docker build -f docker/Dockerfile.vision -t <registry>/vision:latest .
   docker build -f docker/Dockerfile.gateway -t <registry>/gateway:latest .
   ```
5. Deploy containers with the environment variables listed in the table in `README.md` (`DATABASE_URL`, JWT paths/values, service URLs, `NATS_URL`).
6. Smoke test with `scripts/e2e.sh` pointed at the public gateway URL (`API_BASE=https://...`).
7. Document anything not yet automated in your team runbook for follow-up (e.g., blur worker, claims service extraction).
