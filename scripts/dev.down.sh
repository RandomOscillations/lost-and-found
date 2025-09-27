#!/usr/bin/env bash
set -euo pipefail

pushd infra >/dev/null
docker compose down
popd >/dev/null
