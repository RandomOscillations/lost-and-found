⸻

Lost&Found Vision — Backend MVP (Python/FastAPI)

This README is your build sheet. It’s written for you (the dev), not for end users.

Tech choices (per your decisions)
	•	Language/Framework: Python 3.11, FastAPI (Uvicorn/Gunicorn)
	•	Auth: email+password, JWT (RS256)
	•	Storage: Postgres 16 (pgvector), MinIO (S3-compatible)
	•	Vector index: pgvector (simple, one DB)
	•	Embeddings: local CLIP ViT-B/32 (via sentence-transformers or open-clip-torch)
	•	Broker: NATS (simple to run; pub/sub + JetStream optional)
	•	Cache/realtime: Redis (rate limits, WS presence)
	•	Notifications: SMTP (Mailpit/MailHog container)
	•	Privacy: face-blur by default (OpenCV Haar cascade), EXIF scrub

⸻

Monorepo layout

lostfound/
├─ services/
│  ├─ gateway/               # FastAPI gateway: authn, routing, OpenAPI validation
│  ├─ auth/                  # signup/login, JWT, profiles
│  ├─ intake/                # items/media/reports + image worker (blur/thumbnail)
│  ├─ vision/                # embeddings + matches (Top-K)
│  ├─ claims/                # claims + chat (WS)
│  └─ notify/                # email notifications + subscriptions
├─ packages/
│  └─ common/                # pydantic models, event contracts, util (jwt, s3)
├─ infra/
│  ├─ docker-compose.yml
│  ├─ sql/                   # bootstrap SQL (pgvector extension, schemas)
│  ├─ alembic/               # (option) centralized migrations per schema
│  └─ mail/                  # email templates (Jinja)
├─ scripts/
│  ├─ dev.up.sh              # compose up + bootstrap
│  ├─ dev.down.sh
│  ├─ seed.py                # create demo users/items
│  └─ e2e.sh                 # happy-path curl script
├─ docs/
│  ├─ api.html               # your rendered OpenAPI
│  └─ diagrams.md            # mermaid diagrams copied from this README
└─ README.md


⸻

High-level architecture

Current MVP runs the gateway, auth, intake, and vision services as separate FastAPI
processes. They communicate synchronously over HTTP (through the gateway) and share
asynchronous events through NATS (via the shared event bus abstraction in
`packages/common/events.py`).

graph TD
  subgraph Edge
    GW[API Gateway (FastAPI)]
  end

  subgraph Services
    AUTH[Auth & Profiles]
    INTAKE[Intake & Moderation]
    VISION[Vision Matching]
    CLAIMS[Claims & Chat (WS)]
    NOTIF[Notifications]
  end

  GW --> AUTH
  GW --> INTAKE
  GW --> VISION
  GW --> CLAIMS
  GW --> NOTIF

  INTAKE -- ItemCreated/Updated --> NATS[(NATS)]
  VISION -- EmbeddingComputed/MatchesUpdated --> NATS
  CLAIMS -- ClaimOpened/ClaimUpdated/MessagePosted --> NATS
  NOTIF --- NATS

  INTAKE --- MINIO[(MinIO S3)]
  INTAKE --- PG[(Postgres + pgvector)]
  VISION --- PG
  CLAIMS --- PG
  AUTH --- PG
  NOTIF --- REDIS[(Redis)]
  GW --- REDIS

  classDef store fill:#f6f6f6,stroke:#999,stroke-width:1px;
  class MINIO,PG,NATS,REDIS store;

Core flows

Found → Match → Notify

sequenceDiagram
  participant Client
  participant GW as Gateway
  participant IN as Intake
  participant S3 as MinIO
  participant VM as Vision
  participant NT as Notify

  Client->>GW: POST /items/found (presigned flow)
  GW->>IN: validate -> create item+media
  IN-->>S3: process image (blur, thumbnail, strip EXIF)
  IN-->>NATS: publish ItemCreated
  VM-->>NATS: (subscribes) compute embeddings, persist to pgvector
  VM-->>NATS: publish MatchesUpdated
  NT-->>NATS: (subscribes) lookup subscriptions, send emails
  Client->>GW: GET /matches?itemId=...  (optional)

Claim → Verify → Chat

sequenceDiagram
  participant Owner
  participant GW
  participant CL as Claims
  participant IN as Intake

  Owner->>GW: POST /claims
  GW->>CL: create Claim(pending)
  CL-->>Finder: notify (email via Notify)
  Finder->>GW: PATCH /claims/{id} (verify or reject)
  GW->>CL: update claim; if verified -> open WS thread
  Owner<-->GW: WebSocket /threads/{id}/messages (shielded chat)
  CL->>IN: mark item claimed (status update)


⸻

Data model (single Postgres with schemas)

Enable pgvector and create schemas on boot:

-- infra/sql/000_init.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS items;
CREATE SCHEMA IF NOT EXISTS claims;

-- Minimal tables (trim later into service-specific migrations)
-- auth
CREATE TABLE IF NOT EXISTS auth.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  handle TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- items
CREATE TABLE IF NOT EXISTS items.items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL CHECK (type IN ('lost','found')),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  tags TEXT[] DEFAULT '{}',
  zone TEXT,
  when_ts TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'active',
  owner_id UUID,
  finder_id UUID
);

CREATE TABLE IF NOT EXISTS items.media (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id UUID REFERENCES items.items(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  thumb_url TEXT,
  faces_blurred BOOLEAN DEFAULT true,
  pii_redacted BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS items.embeddings (
  item_id UUID PRIMARY KEY REFERENCES items.items(id) ON DELETE CASCADE,
  modality TEXT NOT NULL CHECK (modality IN ('image','text')),
  vec vector(512) -- CLIP ViT-B/32
);

-- claims
CREATE TABLE IF NOT EXISTS claims.claims (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id UUID NOT NULL REFERENCES items.items(id),
  candidate_id UUID NOT NULL, -- found item id
  claimant_id UUID NOT NULL,  -- user
  finder_id UUID NOT NULL,    -- user
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claims.answers (
  claim_id UUID REFERENCES claims.claims(id) ON DELETE CASCADE,
  question TEXT, answer TEXT
);

CREATE TABLE IF NOT EXISTS claims.threads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_id UUID REFERENCES claims.claims(id) ON DELETE CASCADE,
  last_message_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS claims.messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id UUID REFERENCES claims.threads(id) ON DELETE CASCADE,
  sender_id UUID,
  body TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- simple subscriptions (notify)
CREATE TABLE IF NOT EXISTS items.subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  tag TEXT,
  zone TEXT
);

-- indexes
CREATE INDEX IF NOT EXISTS idx_items_type ON items.items(type);
CREATE INDEX IF NOT EXISTS idx_items_zone ON items.items(zone);
CREATE INDEX IF NOT EXISTS idx_claims_item ON claims.claims(item_id);


⸻

Events (NATS subjects + JSON)
	•	items.created { "itemId": "..." }
	•	items.updated { "itemId": "..." }
	•	vision.embedding.computed { "itemId": "...", "modalities": ["image","text"] }
	•	vision.matches.updated { "itemId": "...", "k": 5 }
	•	claims.opened { "claimId":"...", "itemId":"...", "candidateId":"..." }
	•	claims.updated { "claimId":"...", "status":"verified|rejected|closed" }
	•	chat.message.posted { "threadId":"...", "messageId":"..." }
	•	reports.filed { "reportId":"..." }

Keep payloads tiny; services can hydrate from Postgres when needed.

⸻

Local infra (Docker Compose)

infra/docker-compose.yml (trimmed to essentials)

version: "3.9"
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: lostfound
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./sql:/docker-entrypoint-initdb.d

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio123
    ports: ["9000:9000","9001:9001"]
    volumes: [ "minio:/data" ]

  nats:
    image: nats:2.10
    ports: ["4222:4222"]

  redis:
    image: redis:7
    ports: ["6379:6379"]

  mailpit:
    image: axllent/mailpit
    ports: ["8025:8025","1025:1025"]

  gateway:
    build: ../services/gateway
    env_file: ../services/gateway/.env
    depends_on: [postgres, minio, nats, redis]
    ports: ["8080:8080"]

  auth:
    build: ../services/auth
    env_file: ../services/auth/.env
    depends_on: [postgres, nats]

  intake:
    build: ../services/intake
    env_file: ../services/intake/.env
    depends_on: [postgres, minio, nats]

  vision:
    build: ../services/vision
    env_file: ../services/vision/.env
    depends_on: [postgres, nats]

  claims:
    build: ../services/claims
    env_file: ../services/claims/.env
    depends_on: [postgres, nats, redis]

  notify:
    build: ../services/notify
    env_file: ../services/notify/.env
    depends_on: [postgres, nats, mailpit]

volumes:
  pgdata: {}
  minio: {}


⸻

Service skeletons (what each does)

services/gateway/main.py
	•	Validates JWT (RS256 public key) and routes requests to services (internal HTTP).
	•	Optional: apply OpenAPI request/response validation via pydantic models matching your spec.
	•	Exposes WebSocket endpoint for chat that proxies to claims (or keep WS inside claims and have frontend connect directly—your call).

services/auth
	•	/auth/signup (email, password) → create user, hash with argon2/bcrypt.
	•	/auth/login → return JWT (RS256) + refresh token if you want.
	•	/me → profile.
	•	Issues role=moderator manually via seed.

services/intake
	•	POST /items/lost|found GET /items GET /items/{id} POST /reports
	•	Pre-signed upload: POST /media/presign → client PUT to MinIO.
	•	Worker: on new object, blur faces (opencv-python Haar cascade) + create thumbnail + remove EXIF (Pillow). Update media.
	•	Publish items.created/items.updated.

services/vision
	•	Subscribes items.created/items.updated.
	•	Builds CLIP embeddings:
	•	sentence-transformers==2.7 with clip-ViT-B-32 or open-clip-torch (512 dims).
	•	Upserts into items.embeddings.
	•	/matches?itemId=&k= → ANN via pgvector: ORDER BY vec <#> query_vec LIMIT k.
	•	Returns candidates + light explanation: overlap of tags/zone + score.

services/claims
	•	POST /claims, GET/PATCH /claims/{id}
	•	On verify: create threads + enable WebSocket room.
	•	/threads/{id}/messages:
	•	GET (paginated)
	•	WS /threads/{id}/ws → authenticate → join room → broadcast to Redis pub/sub.
	•	PATCH “verified” also soft-locks finder contact info.

services/notify
	•	Listens to vision.matches.updated, claims.updated.
	•	Emails via SMTP (Mailpit @ localhost:1025):
	•	subject: “New match for your lost item”
	•	include link/ID for claim start.

⸻

Environment files (templates)

services/intake/.env (similar for others)

DATABASE_URL=postgresql://postgres:postgres@postgres:5432/lostfound
S3_ENDPOINT=http://minio:9000
S3_BUCKET=lfs-media
S3_ACCESS_KEY=minio
S3_SECRET_KEY=minio123
NATS_URL=nats://nats:4222
JWT_PUBLIC_KEY_PATH=/run/keys/jwt.pub
JWT_ISSUER=lostfound

services/auth/.env

DATABASE_URL=postgresql://postgres:postgres@postgres:5432/lostfound
JWT_PRIVATE_KEY_PATH=/run/keys/jwt.key
JWT_PUBLIC_KEY_PATH=/run/keys/jwt.pub
JWT_ISSUER=lostfound

services/vision/.env

DATABASE_URL=postgresql://postgres:postgres@postgres:5432/lostfound
NATS_URL=nats://nats:4222
EMBEDDING_MODEL=clip-ViT-B-32

(Repeat minimal vars for claims/notify/gateway. Mount /run/keys in compose or generate in container entrypoint.)

⸻

Face blur worker (pseudo-code)

# services/intake/worker.py
import cv2, PIL.Image as Image, piexif, io
from minio import Minio

def blur_faces(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    cvimg = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    faces = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    for (x,y,w,h) in faces.detectMultiScale(cvimg, 1.2, 5):
        roi = cvimg[y:y+h, x:x+w]
        cvimg[y:y+h, x:x+w] = cv2.GaussianBlur(roi, (51,51), 0)
    out = Image.fromarray(cv2.cvtColor(cvimg, cv2.COLOR_BGR2RGB))
    bio = io.BytesIO()
    out.save(bio, format="JPEG", quality=88)
    return bio.getvalue()

def strip_exif(jpeg_bytes: bytes) -> bytes:
    return piexif.remove(jpeg_bytes)


⸻

Embeddings + matches (pseudo-code)

# services/vision/matching.py
from sentence_transformers import SentenceTransformer
import numpy as np
import psycopg

model = SentenceTransformer("clip-ViT-B-32")

def image_embed(pil_img) -> np.ndarray:
    return model.encode(pil_img, convert_to_numpy=True, normalize_embeddings=True)

def topk_for_item(conn, item_id, k=5):
    # fetch item embedding
    vec = conn.execute("SELECT vec FROM items.embeddings WHERE item_id=%s", (item_id,)).fetchone()[0]
    # ivfflat index optional; basic pgvector cosine distance
    rows = conn.execute("""
       SELECT i.id, i.title, i.tags, 1 - (e.vec <#> %s::vector) AS score
       FROM items.embeddings e
       JOIN items.items i ON i.id = e.item_id
       WHERE i.type='found' AND i.status='active' AND i.id <> %s
       ORDER BY e.vec <#> %s::vector
       LIMIT %s
    """, (vec, item_id, vec, k)).fetchall()
    return rows


⸻

Build & run

One-time

```bash
# from repo root
cd infra
POSTGRES_PORT=55432 docker compose up -d --build   # override the host port if 5432 is busy
# spins up Postgres (pgvector), Redis, NATS, MinIO, Mailpit
cd ..
```

The gateway app runs locally via uvicorn (see below). Compose does not yet include per-service application containers; lift-and-shift when you break the gateway back into services.

If you override the host port, remember to point the app at it, e.g.

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/lostfound
```

Create MinIO bucket (first time):

docker exec -it $(docker ps -qf name=minio) sh -lc '
mc alias set local http://127.0.0.1:9000 minio minio123 || true
mc mb -p local/lfs-media || true
'

Gateway MVP (single process)

```bash
python -m pip install -e .
uvicorn lostfound.main:app --reload
```

The FastAPI app seeds `infra/seed/questions.json` into Postgres at startup and exposes the full OpenAPI documented in docs/api.html via a single gateway. Keep the existing service directories for lift-and-shift later.

### Run services independently

Each domain now has its own FastAPI app. Run them in separate terminals (default ports can be overridden via `AUTH_SERVICE_URL`, `INTAKE_SERVICE_URL`, `VISION_SERVICE_URL`):

```bash
# Auth service
export JWT_PRIVATE_KEY_PATH=$(pwd)/infra/keys/jwt.key
export JWT_PUBLIC_KEY_PATH=$(pwd)/infra/keys/jwt.pub
uvicorn services.auth_service.app:app --reload --port 8001

# Intake service
uvicorn services.intake_service.app:app --reload --port 8002

# Vision service
uvicorn services.vision_service.app:app --reload --port 8003

# Gateway (proxies to the services above and also hosts claims/notify)
export AUTH_SERVICE_URL=http://127.0.0.1:8001
export INTAKE_SERVICE_URL=http://127.0.0.1:8002
export VISION_SERVICE_URL=http://127.0.0.1:8003
export JWT_PRIVATE_KEY_PATH=$(pwd)/infra/keys/jwt.key
export JWT_PUBLIC_KEY_PATH=$(pwd)/infra/keys/jwt.pub
uvicorn lostfound.main:app --reload --port 8000
```

With all services running, the existing `./scripts/e2e.sh` script exercises the full flow against the gateway (`API_BASE` defaults to `http://127.0.0.1:8000`).

### Compose helpers

Prefer Docker? Use the helper scripts:

```bash
./scripts/dev.up.sh    # builds & starts postgres, redis, nats, minio, mailpit, auth, intake, vision, gateway
./scripts/dev.down.sh  # stops and removes containers
```

Ports default to 8000–8003 (gateway + three services). Override by exporting `POSTGRES_PORT`, `AUTH_SERVICE_URL`, `INTAKE_SERVICE_URL`, or `VISION_SERVICE_URL` before running the script.

### Service processes & required env

| Service | Entry point | Default port | Required env |
| --- | --- | --- | --- |
| Gateway | `lostfound.main:app` | 8000 | `AUTH_SERVICE_URL`, `INTAKE_SERVICE_URL`, `VISION_SERVICE_URL`, `NATS_URL`, JWT key paths |
| Auth | `services.auth_service.app:app` | 8001 | `DATABASE_URL`, JWT key paths, `NATS_URL` |
| Intake | `services.intake_service.app:app` | 8002 | `DATABASE_URL`, `AUTH_SERVICE_URL`, JWT key paths, `NATS_URL` |
| Vision | `services.vision_service.app:app` | 8003 | `DATABASE_URL`, JWT key paths, `NATS_URL` |

When `NATS_URL` is set the shared event bus publishes and subscribes through that broker; if it is unset the services fall back to in-process handlers (useful for unit tests, but the distributed deployment expects NATS).

See `docs/runbooks.md` for a deeper walkthrough of local development, database bootstrap, and first deploy steps.

### Development commands

```bash
# Run unit test suites (shared + individual services)
python -m unittest tests.test_common tests.test_auth_service tests.test_intake_service tests.test_vision_service

# Quick static check (compilation)
python -m compileall packages services lostfound

# End-to-end happy path (requires services running or compose stack)
./scripts/e2e.sh

# Format/organise imports with Ruff (optional)
ruff format
```

Install Ruff for formatting/linting with `python -m pip install ruff` if you want automatic format enforcement.


⸻

E2E: happy-path check (scripts/e2e.sh)

Run this once the API is up (requires `jq`):

```bash
./scripts/e2e.sh
```

The script spins up unique users, creates found/lost posts, fetches matches, opens a claim with curated + custom answers, then verifies the claim as the finder.

To hit the gateway through ngrok or another tunnel, export `API_BASE` before running the script, for example:

```bash
ngrok http 8000
export API_BASE=https://<your-ngrok-subdomain>.ngrok-free.app
./scripts/e2e.sh
```


⸻

Rate limits & security
	•	Add a simple Redis token bucket in gateway: 60 req/min per JWT sub.
	•	Protect write endpoints with @requires_auth(role='user'); add moderator-only flag check for moderation endpoints.
	•	Enforce idempotency for POST /items/* via Idempotency-Key header (store keys in Redis with 5m TTL).

⸻

Observability
	•	Add /healthz & /readyz on each service.
	•	Use structlog or loguru JSON logs; include request_id header & user id.
	•	Wire OpenTelemetry later (optional for MVP).

⸻

Troubleshooting
	•	No matches? Ensure embeddings exist: check items.embeddings row for the item; verify 512-dim vector and index.
	•	Images not blurred? Confirm worker picked the object; try a face-heavy test photo; check faces_blurred flag.
	•	JWT invalid? Keys mismatch—ensure gateway and auth share the same public key.
	•	Email not arriving? Open Mailpit UI at http://localhost:8025.

⸻

Backlog after MVP
	•	Rerank by zone/time distance; learn from bookmarks/dismissals.
	•	Moderator console; trust scores for reporters.
	•	Push notifications; SSO; meet-up location suggestions.
	•	Social media ingestion (Snap etc.) with a moderation queue.
	•	Split the claims and notify services out of the gateway once chat/notifications mature.
	•	Restore the computer-vision blur worker as a standalone job (ties back into intake media hooks).
