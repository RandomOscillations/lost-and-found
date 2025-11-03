A3: Design Analysis & Improvement — Lost&Found Vision (Concise)

Author(s): Adithya Srinivasan
Course: CSC491/591 — Software Analysis & Design
Date: Oct 02, 2025

Project (1 paragraph)

Lost & Found Vision is a microservice-based FastAPI system that helps reunite found items with their owners while minimizing exposure and fraud. The monorepo runs four cooperating services: a gateway (public API, auth validation, proxying), Auth (signup/login/JWT), Intake (lost/found items, media metadata, prompts, subscriptions/reports), and Vision (candidate matching). Postgres 16 backs persistence (pgvector-ready), Redis/NATS are available for rate limits and events, and MinIO/Mailpit emulate S3/SMTP. The core flow is Found → Match → Claim/Verify (prompts) with a notify stub for later chat/updates. Swagger at the gateway and a tiny Bootstrap UI enable demos; an e2e script validates the happy path.

⸻

Red Flags & Design Principles (concise list)

Instructions: For each red flag below, fill the Context, paste a tiny Before snippet (5–15 lines max), and name the Design Principle you’d apply to remove it. A one-line Intended Fix (principle-level) is enough. No full implementation required.

1) Embeddings table prevents multiple modalities; no ANN index
    • Context: services/vision_service/service.py (matching heuristics)
    • Red Flag (what/why): The MVP has no embeddings table; we can’t store both image and text vectors per item nor leverage ANN indices. Scaling Top‑K will be slow and quality limited.
    • Before (excerpt):
```py
stmt = (
    select(Item)
    .where(
        Item.type == counterpart_type,
        Item.status == ItemStatus.ACTIVE,
        Item.id != target_item.id,
    )
)
# scoring uses tags/category/zone/time — no vector similarity
```
    • Design Principle: Correctness, Performance / Appropriate Data Structures
    • Intended Fix (principle-level): Introduce `embeddings(item_id, modality, vec vector(512))` with composite PK `(item_id, modality)` and an ANN index (ivfflat + cosine). Background job computes vectors; Vision queries pgvector for fast Top‑K.

⸻

2) POSTs are non-idempotent (duplicates on retry)
    • Context: lostfound/gateway/intake.py; lostfound/services/claims/router.py
    • Red Flag: Retries can create duplicate items/claims; unsafe under network glitches or browser resubmits.
    • Before (excerpt):
```py
@router.post("/items/found")
async def create_found(payload: FoundItemCreate, request: Request):
    return await forward_request(
        request, base_url=_base(), path="/items/found", json_body=payload,
    )
```
    • Design Principle: Idempotent Receiver, Robustness
    • Intended Fix: Gateway enforces `Idempotency-Key` with a Redis TTL store; identical request bodies within TTL return the original response; conflicting replays → 409.

⸻

3) Unbounded lists & inconsistent errors
    • Context: `/items` (Intake), `/threads/{id}/messages` (Claims), error envelopes
    • Red Flag: No pagination; varied error shapes → fragile clients and heavy responses.
    • Before (excerpt):
```py
async def search_items(...)-> list[Item]:
    stmt = select(Item).order_by(Item.created_at.desc())
    result = await self.session.execute(stmt)
    return result.scalars().all()  # unbounded
```
```py
result = await self.session.execute(
    select(ThreadMessage).where(ThreadMessage.thread_id == thread_id)
)
return result.scalars().all()  # unbounded
```
    • Design Principle: Design by Contract, Consistency
    • Intended Fix: Add `page/limit` query params, `X-Total-Count` header, and a standard error envelope `{error:{code,message,traceId}}` across services.

⸻

4) Events lack versioning & correlation (hard to evolve/trace)
    • Context: packages/common/events.py; publishers in gateway/claims
    • Red Flag: Bare payloads (e.g., `{ "itemId": "…" }`); no `traceId`, no version → difficult evolution and cross-service tracing.
    • Before (excerpt):
```py
async def publish(self, event: str, payload: dict) -> None:
    if self._nats_url:
        await client.publish(self._full_subject(event), json.dumps(payload).encode())
    await self._dispatch_local(event, payload)  # no envelope/version/trace
```
    • Design Principle: Evolutionary Design, Observability
    • Intended Fix: Event envelope `{type,v,traceId,occurredAt,data}`; propagate/require `X-Request-ID` as `traceId`; version topics by subject prefix (`lostfound.v1.items.created`).

⸻

5) Shared ORM models across services (tight coupling)
    • Context: multiple services import `packages/common/models`
    • Red Flag: Cross-context ORM reuse couples services/data; makes independent evolution risky.
    • Before (excerpt):
```py
from packages.common.models import User, UserRole  # in auth
...
from packages.common.models import Item, ItemMedia, ItemPrompt  # in intake
```
    • Design Principle: Encapsulation / Bounded Contexts, Information Hiding
    • Intended Fix: 

⸻

6) Schema drift risk (startup create_all(); no migrations)
    • Context: services/auth_service/app.py; lostfound/main.py startup
    • Red Flag: Non-reproducible DB shape; CI can’t verify changes or rollbacks.
    • Before (excerpt):
```py
@app.on_event("startup")
async def _startup():
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```
    • Design Principle: Reliability / Repeatability
    • Intended Fix: Alembic per domain; run `upgrade head` in CI/CD; gate PRs on migration diffs.

⸻

7) Missing rate limits on write endpoints (abuse risk)
    • Context: Gateway routers; `rate_limit_per_minute` exists in settings but unused
    • Red Flag: No throttling → spam/DoS risk; noisy neighbors.
    • Before (excerpt):
```py
rate_limit_per_minute: int = Field(default=60, ge=1)  # not enforced
```
    • Design Principle: Safety, Resource Governance
    • Intended Fix: Redis token bucket keyed by JWT `sub`; return `429` with `Retry-After`; count per-route weights.

⸻

8) Weak observability at boundaries (no request IDs)
    • Context: Gateway app config; logs and events
    • Red Flag: Can’t trace a user action across services.
    • Before (excerpt):
```py
logging.basicConfig(level=logging.INFO)
# no request-id middleware/correlation headers; event bus also lacks traceId
```
    • Design Principle: Observability, Transparency
    • Intended Fix: Correlation middleware sets/propagates `X-Request-ID`; include `traceId`, route, latency, user in structured logs; add event trace propagation.

⸻
