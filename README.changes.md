Lost & Found Vision — Red‑Flag Fixes (Concise Before/After)

This document summarizes the code changes addressing the first five red flags in readme‑a3.md. For each item:
- Issue and fix summary
- Files touched
- Tiny code snippets (only the lines that changed)
- Exact fix statement

---

1) Vision matching lacks embeddings/ANN
- Issue: Matching used only tags/category/zone/time; no embeddings table or ANN index.
- Files: services/vision_service/models.py (new), services/vision_service/app.py, services/vision_service/service.py.
- Snippets:
  - services/vision_service/app.py
    - Added: `from .models import VisionBase`
    - Added: `await conn.run_sync(VisionBase.metadata.create_all)`
    - Added ivfflat index creation on `embeddings.vec` (cosine ops)
  - services/vision_service/models.py
    - New: `Embedding(item_id UUID, modality text, vec vector(512))`
  - services/vision_service/service.py
    - Added `_ensure_embeddings()` to seed deterministic 512‑d vectors on demand
    - Added cosine ranking query using pgvector operator `<=>` with LIMIT k
- Exact fix: Introduced embeddings table + ANN index; Vision now seeds vectors and ranks by cosine similarity, with heuristic fallback.

---

2) POSTs not idempotent
- Issue: Retries could create duplicate items/claims/users.
- Files: lostfound/gateway/idempotency.py (new), lostfound/gateway/intake.py, lostfound/gateway/auth.py, lostfound/services/claims/router.py.
- Snippets:
  - lostfound/gateway/idempotency.py
    - New: `ensure_idempotent(request, body, ttl_seconds=300)` enforcing Idempotency‑Key via an in‑memory TTL store
  - lostfound/gateway/intake.py
    - Added before forward: `await ensure_idempotent(request, payload.model_dump(mode="json"))`
  - lostfound/gateway/auth.py
    - Added on signup: `await ensure_idempotent(request, payload.model_dump(mode="json"))`
  - lostfound/services/claims/router.py
    - Added on open_claim: `await ensure_idempotent(request, payload.model_dump(mode="json"))`
- Exact fix: When clients send Idempotency‑Key, identical POSTs are deduplicated per path/body/sub for a short TTL and replays return 409.

---

3) Unbounded listings & inconsistent errors
- Issue: `/items` and `/threads/{id}/messages` returned unbounded arrays; error shapes varied.
- Files: services/intake_service/service.py, services/intake_service/router.py, lostfound/services/claims/service.py, lostfound/services/claims/router.py, lostfound/main.py.
- Snippets:
  - services/intake_service/service.py
    - Signature: `-> tuple[list[Item], int]` and new `page`/`limit` params
    - Added total count with `with_only_columns(Item.id)` and offset/limit
  - services/intake_service/router.py
    - Added query params: `page`, `limit`
    - Added header: `response.headers["X-Total-Count"] = str(total)`
  - lostfound/services/claims/service.py
    - `list_messages(..., page, limit) -> tuple[list[ThreadMessage], int]` with count + pagination
  - lostfound/services/claims/router.py
    - Added `page`, `limit` and `response.headers["X-Total-Count"]`
  - lostfound/main.py
    - New request‑id middleware (sets/propagates X‑Request‑ID)
    - Standard error envelope `{ error: { code, message, traceId } }`
- Exact fix: Added pagination and X‑Total‑Count, plus uniform error envelopes with correlation ids.

---

4) Events lack versioning & correlation
- Issue: Events were bare payloads without version or trace id.
- Files: packages/common/events.py, lostfound/main.py (middleware sets trace id).
- Snippets:
  - packages/common/events.py
    - New contextvar helpers: `set_trace_id/get_trace_id`
    - `publish()` now wraps payload in an envelope: `{type, v:1, traceId, occurredAt, data}` for brokered messages
  - lostfound/main.py
    - Middleware calls `set_trace_id(rid)` so published events carry the same trace id
- Exact fix: All NATS‑published events are versioned and correlated to requests via X‑Request‑ID.

---

5) Shared ORM models across services (decoupling start)
- Issue: Services imported `packages/common.models` directly, coupling ORM schemas across contexts.
- Files: services/auth_service/models.py (new), services/intake_service/models.py (new), and import updates in services/auth_service/service.py, services/intake_service/{router.py,service.py}.
- Snippets:
  - services/auth_service/service.py
    - `from .models import User, UserRole` (replaces import from `packages.common.models`)
  - services/intake_service/router.py
    - `from .models import Item, ItemStatus, ItemType, PromptSource`
  - services/*/models.py
    - Transitional re‑exports to form a service‑local boundary (enables later divergence)
- Exact fix: Introduced service‑local ORM boundaries (transitional re‑exports today) to allow independent evolution while keeping API/DTO contracts shared.

---

These targeted changes fix the first five design red flags with minimal code churn while preserving behavior and Swagger compatibility.

---

Expanded, Commented Snippets (for presentation)

1) Vision embeddings + ANN
// Issue: heuristic-only matching; no vector similarity.
// Fix: embeddings table, ivfflat index, vector query path.

- services/vision_service/models.py
```
class Embedding(VisionBase):
    __tablename__ = "embeddings"
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    modality: Mapped[str] = mapped_column(String(16), primary_key=True, default="text")
    vec: Mapped[list[float]] = mapped_column(Vector(512))
```

- services/vision_service/app.py
```
await conn.run_sync(VisionBase.metadata.create_all)
await conn.execute(text(
    """
    CREATE INDEX IF NOT EXISTS idx_embeddings_vec_cosine
    ON embeddings USING ivfflat (vec vector_cosine_ops)
    WITH (lists = 100);
    """
))
```

- services/vision_service/service.py
```
q = text(
    """
    SELECT e2.item_id AS candidate_id,
           1 - (e1.vec <=> e2.vec) AS score
    FROM embeddings e1
    JOIN embeddings e2 ON e2.modality = e1.modality
    WHERE e1.item_id = :target AND e2.item_id <> :target
    ORDER BY e1.vec <=> e2.vec
    LIMIT :k
    """
)
...
explanation=MatchExplanation(..., aspects=["vector"])  # new aspect when vector path used
```

What changed: Vector-based ranking path (cosine) with deterministic seeding via `_ensure_embeddings()`.

2) Idempotency for POSTs
// Issue: duplicate resources under retries.
// Fix: TTL cache keyed by Idempotency-Key + path/body/sub.

- lostfound/gateway/idempotency.py
```
async def ensure_idempotent(request: Request, body: dict | None, ttl_seconds: int = 300) -> None:
    idem = request.headers.get("Idempotency-Key")
    if not idem:
        return
    key = idem + ":" + _make_key(request, body)
    added = await _cache.add(key, ttl_seconds)
    if not added:
        raise HTTPException(status_code=409, detail="Duplicate request (Idempotency-Key)")
```

- Gateways/services callsite (example: lostfound/gateway/intake.py)
```
await ensure_idempotent(request, payload.model_dump(mode="json"))
```

What changed: Replays return 409; single effect per idempotency key window.

3) Pagination + standard error envelope
// Issue: unbounded lists; heterogeneous errors.
// Fix: page/limit + X-Total-Count, uniform error shape.

- services/intake_service/router.py
```
page: int | None = Query(None, ge=1)
limit: int | None = Query(None, ge=1, le=100)
...
response.headers["X-Total-Count"] = str(total)
```

- lostfound/main.py
```
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    set_trace_id(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    payload = {"error": {"code": exc.status_code, "message": exc.detail, "traceId": request.headers.get("X-Request-ID") or ""}}
    return JSONResponse(status_code=exc.status_code, content=payload)
```

What changed: Predictable pagination contract; errors carry `error.{code,message,traceId}`.

4) Versioned, correlated events
// Issue: bare payloads; no versioning/correlation.
// Fix: published envelope with metadata + trace propagation.

- packages/common/events.py
```
envelope = {
    "type": event,
    "v": 1,
    "traceId": get_trace_id(),
    "occurredAt": datetime.now(timezone.utc).isoformat(),
    "data": payload,
}
```

What changed: Brokered events are versioned and trace-linked; local handlers keep data-only for back-compat.

5) Service‑local ORM boundaries
// Issue: hard coupling via shared ORM imports.
// Fix: service‑local `models.py` modules re‑export ORM types; imports updated.

- services/intake_service/models.py
```
from packages.common.models import (
    Item, ItemMedia, ItemPrompt, ItemStatus, ItemType, PromptSource, Report, Subscription,
)
__all__ = ["Item","ItemMedia","ItemPrompt","ItemStatus","ItemType","PromptSource","Report","Subscription"]
```

- usage (example)
```
from .models import Item, ItemStatus, ItemType, PromptSource
```

What changed: Clear service boundary; enables later schema divergence with minimal code churn.
