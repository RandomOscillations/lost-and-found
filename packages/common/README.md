# packages/common

This package houses the shared building blocks that every service imports. Treat it as the
"platform" layer: the primitives here should be stable, backwards compatible, and free of
service-specific branching. Anything a single service owns should stay in that service's
package instead of landing here.

## Contents

| Module | Purpose |
| --- | --- |
| `config.py` | Pydantic settings used to read environment variables (database URL, JWT paths, service URLs, etc.). |
| `db.py` | Async SQLAlchemy engine + session factory wired from the shared settings. Services can override the dependency in tests. |
| `events.py` | Lightweight event bus abstraction (currently in-process for the MVP) that surfaces a consistent publish/subscribe interface. |
| `jwt.py` | RSA key loading + token encode/decode helpers used by auth, gateway, and downstream services. |
| `models/` | Declarative SQLAlchemy models that map to our Postgres schemas (users, items, claims, prompts, question bank, etc.). |
| `question_bank.py` | Loader that seeds the curated verification prompts from `infra/seed/questions.json` into the database. |
| `schemas/` | Pydantic DTOs shared across service boundaries (auth/login payloads, item outputs, claim payloads). |
| `security.py` | Password hashing/verifying helpers (Passlib bcrypt wrapper). |
| `utils/` | Cross-cutting helpers (category inference, time helpers). |

## When to add something here

Use `packages/common` when all services need the same implementation (e.g. signing keys,
canonical ORM models, shared response schemas). If the logic is only needed by one service,
keep it close to that service so that other teams don't get unnecessary coupling.

Changes in this package should remain backwards compatible. When you add a breaking change,
coordinate a lock-step update across all services and bump the version in the service Docker
images.

## Testing

The shared components are covered by `tests/test_common.py`. If you add new utilities or
schema behaviour, extend that test suite before relying on it from a service.
