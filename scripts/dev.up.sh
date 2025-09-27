#!/usr/bin/env bash
set -euo pipefail

pushd infra >/dev/null
POSTGRES_PORT=${POSTGRES_PORT:-55432}
export POSTGRES_PORT
AUTH_SERVICE_URL=${AUTH_SERVICE_URL:-http://127.0.0.1:8001}
INTAKE_SERVICE_URL=${INTAKE_SERVICE_URL:-http://127.0.0.1:8002}
VISION_SERVICE_URL=${VISION_SERVICE_URL:-http://127.0.0.1:8003}
docker compose up -d --build
popd >/dev/null

cat <<INFO
Services are starting. Exposed ports:
  Gateway:              http://127.0.0.1:8000
  Auth service:         http://127.0.0.1:8001
  Intake service:       http://127.0.0.1:8002
  Vision service:       http://127.0.0.1:8003
  Postgres:             localhost:${POSTGRES_PORT}
INFO
