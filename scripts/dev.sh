#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$ROOT/backend" && . .venv/bin/activate && uvicorn app.main:app --port 8000) &
(cd "$ROOT/frontend" && npm run dev) &
wait
