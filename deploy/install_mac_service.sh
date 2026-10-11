#!/usr/bin/env bash
# Install (or reinstall) the Universe IO server as a macOS LaunchAgent.
#   deploy/install_mac_service.sh /path/to/python ["https://universe-io.fun,https://www.universe-io.fun"]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${1:?usage: $0 /path/to/python [allowed-origins]}"
ORIGINS="${2:-https://universe-io.fun,https://www.universe-io.fun}"
LOGS="$HOME/Library/Logs/universe-io"
PLIST="$HOME/Library/LaunchAgents/fun.universe-io.server.plist"
mkdir -p "$LOGS" "$HOME/Library/LaunchAgents"
"$PYTHON" -c "import fastapi, uvicorn" || { echo "install requirements first: $PYTHON -m pip install -r requirements.txt"; exit 1; }
sed -e "s#__REPO__#$REPO#g" -e "s#__PYTHON__#$PYTHON#g" -e "s#__ORIGINS__#$ORIGINS#g" -e "s#__LOGS__#$LOGS#g" \
  "$REPO/deploy/fun.universe-io.server.plist.template" > "$PLIST"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
sleep 2
curl -fsS http://127.0.0.1:8000/healthz && echo && echo "Universe IO server is running. Logs: $LOGS/server.log"
