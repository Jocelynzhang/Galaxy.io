#!/usr/bin/env bash
# Production server: no auto-reload, listens only on this machine (cloudflared connects locally
# and is the only way in from the internet).
#   GALAXY_PYTHON           python with requirements.txt installed (default: python on PATH)
#   GALAXY_PORT             default 8000
#   GALAXY_ALLOWED_ORIGINS  e.g. "https://universe-io.fun,https://www.universe-io.fun"
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${GALAXY_PYTHON:-python}"
exec "$PY" -m uvicorn server.main:app \
  --host 127.0.0.1 --port "${GALAXY_PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips 127.0.0.1 \
  --ws-max-size 4096 --no-access-log --log-level info
