#!/usr/bin/env bash
set -euo pipefail

PORT=${PORT:-5173}
DIR="$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)/ui"

printf 'Serving UI from %s on http://127.0.0.1:%s\n' "$DIR" "$PORT"
python -m http.server "$PORT" --directory "$DIR"
