# Lost & Found Vision — Current Status & Architecture

This document captures the present state of the Lost & Found Vision project: what’s implemented, how the services are orchestrated, key runtime details, and near‑term improvement areas.

## What’s Implemented

- Core user journeys end‑to‑end via the gateway:
  - Sign up / Login (JWT, RS256) → bearer auth
  - Finder posts a found item (+ curated + optional custom prompts)
  - Owner posts a lost item
  - Retrieve candidate matches for a lost item
  - Owner opens a claim (must answer curated + custom prompts)
  - Finder verifies or rejects the claim; owner can fetch claim status
- Swagger docs exposed at the gateway (`/docs`) with bearer security
- Lightweight Bootstrap UI for manual testing in `ui/`
- e2e script (`scripts/e2e.sh`) validates the happy path automatically

## Microservices & Responsibilities

- Gateway (FastAPI, `lostfound.main:app`, port 8000)
  - Validates JWTs (RS256 public key), applies CORS, exposes unified OpenAPI
  - Proxies to domain services over internal HTTP (httpx client)
  - Hosts the claims router (MVP scope) and a notify stub (event consumers)
  - Subscribes/publishes domain events via the shared bus (NATS if configured)

- Auth Service (FastAPI, `services.auth_service.app:app`, port 8001)
  - Endpoints: `/auth/signup`, `/auth/login`, `/auth/me`
  - Password hashing via passlib/bcrypt; issues JWT access tokens (RS256)
  - Shared DB models from `packages/common/models` (`users` table)

- Intake Service (FastAPI, `services.intake_service.app:app`, port 8002)
  - Endpoints: `/items/found`, `/items/lost`, `/items/{id}`, `/items`, `/subscriptions`, `/reports`
  - Persists items, media, prompts; seeds a curated question bank by category
  - Publishes `items.created` for downstream match updates / notifications

- Vision Service (FastAPI, `services.vision_service.app:app`, port 8003)
  - Endpoint: `/matches?itemId=...&k=...`
  - Returns similarity candidates using text/tags/category/zone/time (pgvector‑ready layout; pure SQL ranking stub for MVP)

- Shared Foundations (`packages/common`)
  - Config (`pydantic-settings`), async SQLAlchemy engine/session, JWT helpers
  - Declarative ORM for `users`, `items`, `item_media`, `item_prompts`, `claims`, `claim_answers`, `claim_threads`, `thread_messages`, `subscriptions`, `reports`, `question_bank`
  - Event bus abstraction (`events.py`) with NATS integration when `NATS_URL` is set; falls back to in‑process publish/subscribe for local tests
  - Pydantic schemas used across service boundaries (auth, items, claims)

## Orchestration & Runtime

- Docker compose (`infra/docker-compose.yml`) brings up: Postgres (pgvector image), Redis, NATS, MinIO, Mailpit, and the four FastAPI apps
- Services share RSA keys via bind‑mount (`infra/keys/jwt.key` + `jwt.pub`)
- DB bootstrapping uses SQLAlchemy `create_all()` on startup; optional SQL bootstrap scripts live in `infra/sql/`
- Gateway OpenAPI is augmented with a `BearerAuth` security scheme and global security requirement so Swagger automatically includes the bearer token once authorized
- CORS allow‑list includes `http://127.0.0.1:5173`, `http://localhost:5173`, and `http://[::1]:5173` for the local UI

## How to Run & Test

- Start everything:
  - `POSTGRES_PORT=55432 ./scripts/dev.up.sh`
- Unit tests:
  - `python -m unittest tests.test_common tests.test_auth_service tests.test_intake_service tests.test_vision_service`
- Happy‑path:
  - `./scripts/e2e.sh` (creates users, posts found/lost, gets matches, opens & verifies a claim)
- Swagger walkthrough:
  - `http://127.0.0.1:8000/docs` → `POST /auth/login` to get a token → Authorize with `Bearer <token>`
  - Use finder token for `/items/found`; owner token for `/items/lost` and `/claims`
- Optional UI:
  - `./scripts/ui.dev.sh` → `http://127.0.0.1:5173`

## Data Flow Summary

- Create found item in Intake → Intake publishes `items.created`
- Gateway listens and calls Vision to refresh matches (MVP in‑process invocation; NATS topic available)
- Owner gets candidates via Gateway → Vision
- Owner opens a claim via Gateway → Claims service layer (embedded in gateway for MVP)
- Finder verifies claim → claim status updated; event `claims.updated` emitted (notify stub consumes)

## Current Limits & Assumptions

- Claims and notify logic run inside the gateway process (kept modular to split later)
- Images are treated as URLs (MinIO path); no presign/upload flow in MVP
- Matching is a heuristic over tags/category/zone/time; vector embeddings are stubbed
- Migrations use `create_all()` instead of Alembic; tables live in the public schema
- Rate limiting and idempotency are stubbed/not enforced yet

## Improvement Areas (Next Steps)

1. Extract **Claims** and **Notify** into standalone services
   - Add service‑level OpenAPI, isolated DB sessions, and NATS subscriptions
   - Move question‑bank warmup to Claims service startup
2. Introduce **Alebmic migrations** and schema scoping per domain
   - Replace `create_all()`; add CI to verify migration drift
3. Implement **media ingestion** with presigned URLs and a **blur/thumbnail worker**
   - Async tasks or a separate worker process; EXIF scrubbing; safety signals persisted
4. Add **rate limiting** and **idempotency keys** at the gateway
   - Redis token bucket (e.g., 60 req/min per `sub`); `Idempotency-Key` header support for POSTs
5. Upgrade **matching** with vector embeddings (e.g., CLIP ViT‑B/32) and pgvector indexes
   - Background embedding computation; approximate nearest neighbor; re‑rank by zone/time distance
6. Harden **security**: refresh tokens, key rotation, and JTI replay protection
   - Optionally add OIDC/SSO and scopes for moderator endpoints
7. **Observability**: structured JSON logs, request IDs, and OpenTelemetry traces
   - Capture audit events for claims and moderation actions
8. **Docs & DX**: per‑service Swagger UIs, example collections, and a demo data seeder
   - Ship ready‑made Postman/Bruno collections and sample fixtures
9. **Testing**: expand unit + contract tests, add integration tests across services
   - Mock NATS in tests; ephemeral DB via postgres container in CI
10. **Productionization**: health/readiness probes, probes for deps, resource limits
   - K8s manifests or compose‑prod with env overlays

## Quick Reference

- Gateway: `lostfound/main.py` (includes routers from `lostfound/gateway/*` and embedded `claims`)
- Shared: `packages/common` (config, db, jwt, models, schemas, events)
- Services: `services/{auth_service,intake_service,vision_service}`
- Infra: `infra/docker-compose.yml`, keys in `infra/keys/`
- UI: `ui/` (served via `scripts/ui.dev.sh`)

This state is a complete MVP with clean seams for future separation. The demo flows (Swagger/UI/e2e) run against the compose stack and exercise the core value: safely connecting finders and owners with lightweight verification.

