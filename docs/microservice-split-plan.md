# Microservice Split Plan

This checklist captures the work needed to lift the consolidated gateway into distinct deployable services.

## Shared Foundations
- [x] Extract shared models/schemas/settings into `packages/common` (DB models, Pydantic schemas, config, event bus helpers).
- [x] Provide a `common` package README explaining what is shared vs per-service.
- [x] Ensure alembic migrations or SQL bootstrap scripts live in `infra/sql` and are service-agnostic.

## Service: Auth
- [x] Create `services/auth/app.py` exposing `/auth/*` routes with its own FastAPI instance.
- [x] Implement dedicated dependency wiring (DB session, password hashing, JWT keys).
- [x] Add service-specific `.env.example` documenting required environment variables.

## Service: Intake
- [x] Create `services/intake_service/app.py` exposing item/report/subscription endpoints and background publishing.
- [x] Replace in-process event bus usage with HTTP/NATS calls; for MVP keep HTTP backchannel to gateway optional.
- [ ] Handle media processing hooks (presign, blur worker) as background tasks or separate worker module.

## Service: Vision
- [x] Spin up `services/vision_service/app.py` with `/matches` endpoint and subscription to item events.
- [x] Refactor matching logic to consume `common` models, using async DB access scoped to this service.

## Service: Claims
- [ ] Create `services/claims/app.py` exposing `/claims` and `/threads` endpoints plus WS gateway if needed.
- [ ] Move question-bank seeding into this service’s startup (reuse `common/question_bank.py`).
- [ ] Ensure Redis / NATS hooks are configurable.

## Service: Notify (Optional for MVP)
- [ ] Flesh out notification worker that listens to events (matches, claims) and sends emails via Mailpit/SMTP.

## API Gateway
- [x] Trim `lostfound/main.py` into a thin gateway that proxies to the individual services (HTTP client with retries, rate limits, auth validation).
- [x] Update routers to delegate rather than execute business logic directly.
- [x] Maintain `/healthz` and `/readyz` plus auth token verification.

## Infra Updates
- [x] Expand `infra/docker-compose.yml` to run each service container + shared dependencies.
- [x] Add Dockerfiles (or a multi-stage build) per service.
- [x] Provide `scripts/dev.up.sh` / `dev.down.sh` orchestrating compose workflows.
- [x] Document port assignments and inter-service URLs in README.

## Testing & Tooling
- [x] Update `scripts/e2e.sh` to target the gateway once services are split (ensure service startup ordering).
- [x] Add lightweight contract tests per service (pytest + httpx).
- [x] Wire lint/format/test commands into README.

## Documentation
- [x] Update `Readme.md` architecture diagrams to reflect distributed services.
- [x] Add runbooks for local development, migrations, and first deployment.
- [x] Note remaining TODOs and future enhancements after the split.

Track progress by ticking boxes as work completes. Adjust as new requirements emerge.
