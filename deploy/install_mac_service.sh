#!/usr/bin/env bash
# Install (or reinstall) the Galaxy.io server as a macOS LaunchAgent.
#   deploy/install_mac_service.sh /path/to/python ["https://galaxyio.fun,https://www.galaxyio.fun"]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${1:?usage: $0 /path/to/python [allowed-origins]}"
ORIGINS="${2:-https://galaxyio.fun,https://www.galaxyio.fun}"
LOGS="$HOME/Library/Logs/galaxyio"
PLIST="$HOME/Library/LaunchAgents/fun.galaxyio.server.plist"
mkdir -p "$LOGS" "$HOME/Library/LaunchAgents"
"$PYTHON" -c "import fastapi, uvicorn" || { echo "install requirements first: $PYTHON -m pip install -r requirements.txt"; exit 1; }
sed -e "s#__REPO__#$REPO#g" -e "s#__PYTHON__#$PYTHON#g" -e "s#__ORIGINS__#$ORIGINS#g" -e "s#__LOGS__#$LOGS#g" \
  "$REPO/deploy/fun.galaxyio.server.plist.template" > "$PLIST"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
sleep 2
curl -fsS http://127.0.0.1:8000/healthz && echo && echo "Galaxy.io server is running. Logs: $LOGS/server.log"
