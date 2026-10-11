#!/usr/bin/env bash
# One command to host Universe IO on this Mac at https://universe-io.fun. Safe to re-run: every step
# skips what is already done, so it also works as "update to the latest code and restart".
#
#   deploy/start_hosting.sh
#
# What it does:
#   1. installs cloudflared (Homebrew) if missing
#   2. clones or updates the deploy checkout at ~/universe-io (outside ~/Documents: macOS privacy
#      protection stops background services from reading Documents/Desktop/Downloads)
#   3. creates the Python 3.11 env (conda-forge, or a venv) and installs requirements
#   4. installs the game server as a LaunchAgent (fun.universe-io.server)
#   5. logs in to Cloudflare (opens a browser the first time: pick universe-io.fun, click Authorize)
#   6. creates the tunnel, writes ~/.cloudflared/config.yml, points the DNS names at the tunnel
#   7. installs the tunnel as a LaunchAgent (com.cloudflare.cloudflared)
#   8. checks https://universe-io.fun/healthz
#
# Override any of these with environment variables, e.g. DOMAIN=example.fun deploy/start_hosting.sh
DOMAIN="${DOMAIN:-universe-io.fun}"
TUNNEL="${TUNNEL:-universe-io}"
APP_DIR="${APP_DIR:-$HOME/universe-io}"
REPO_URL="${REPO_URL:-git@github.com:Jocelynzhang/Galaxy.io.git}"
BRANCH="${BRANCH:-master}"
ENV_NAME="${ENV_NAME:-galaxyio}"

set -euo pipefail

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mxx %s\033[0m\n' "$*" >&2; exit 1; }

find_conda() {
  local c
  for c in "${CONDA_EXE:-}" "$HOME/miniconda3/bin/conda" "$HOME/miniforge3/bin/conda" \
           "$HOME/anaconda3/bin/conda" /opt/homebrew/bin/conda /opt/homebrew/Caskroom/miniconda/base/bin/conda; do
    [[ -n "$c" && -x "$c" ]] && { echo "$c"; return; }
  done
}

setup_python() {
  local conda base
  conda="$(find_conda || true)"
  if [[ -n "$conda" ]]; then
    base="$("$conda" info --base)"
    PY="$base/envs/$ENV_NAME/bin/python"
    if [[ ! -x "$PY" ]]; then
      # conda-forge only: the Anaconda default channels need a Terms of Service acceptance.
      "$conda" create -y -n "$ENV_NAME" --override-channels -c conda-forge python=3.11 pip
    fi
  else
    PY="$APP_DIR/.venv/bin/python"
    if [[ ! -x "$PY" ]]; then
      command -v python3.11 >/dev/null || brew install python@3.11
      python3.11 -m venv "$APP_DIR/.venv"
    fi
  fi
  "$PY" -m pip install -q --upgrade pip
  "$PY" -m pip install -q -r "$APP_DIR/requirements.txt"
  echo "python: $PY ($("$PY" --version))"
}

tunnel_id() {
  cloudflared tunnel list -o json 2>/dev/null | /usr/bin/python3 -c '
import json, sys
name = sys.argv[1]
print(next((t["id"] for t in json.load(sys.stdin) or [] if t["name"] == name), ""))' "$TUNNEL"
}

install_tunnel_service() {
  # Written by hand: `cloudflared service install` (2026.10) writes a plist that runs bare
  # `cloudflared` without `tunnel run`, so it exits immediately.
  local plist="$HOME/Library/LaunchAgents/com.cloudflare.cloudflared.plist"
  local bin; bin="$(command -v cloudflared)"
  cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.cloudflare.cloudflared</string>
  <key>ProgramArguments</key>
  <array>
    <string>$bin</string>
    <string>tunnel</string>
    <string>run</string>
    <string>$TUNNEL</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>$HOME/Library/Logs/com.cloudflare.cloudflared.out.log</string>
  <key>StandardErrorPath</key>
  <string>$HOME/Library/Logs/com.cloudflare.cloudflared.err.log</string>
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)" "$plist" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$plist"
}

main() {
  [[ "$(uname)" == Darwin ]] || die "this script is for macOS"

  step "1/8 Tools"
  command -v brew >/dev/null || die "install Homebrew first: https://brew.sh"
  command -v git  >/dev/null || die "install git first: xcode-select --install"
  command -v cloudflared >/dev/null || brew install cloudflared
  cloudflared --version

  step "2/8 Code in $APP_DIR"
  case "$APP_DIR" in "$HOME/Documents"*|"$HOME/Desktop"*|"$HOME/Downloads"*)
    die "APP_DIR must be outside ~/Documents, ~/Desktop and ~/Downloads (macOS blocks services there)";;
  esac
  if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" fetch -q origin "$BRANCH"
    git -C "$APP_DIR" checkout -q "$BRANCH"
    git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || die "can't fast-forward $APP_DIR (local changes there?)"
  else
    git clone -q -b "$BRANCH" "$REPO_URL" "$APP_DIR"
  fi
  git -C "$APP_DIR" log --oneline -1

  step "3/8 Python environment"
  setup_python

  step "4/8 Game server service"
  "$APP_DIR/deploy/install_mac_service.sh" "$PY" "https://$DOMAIN,https://www.$DOMAIN"

  step "5/8 Cloudflare login"
  if [[ -f "$HOME/.cloudflared/cert.pem" ]]; then
    echo "already logged in"
  else
    echo "A browser will open: sign in, pick $DOMAIN, click Authorize."
    cloudflared tunnel login
  fi

  step "6/8 Tunnel '$TUNNEL' + DNS"
  local id creds
  id="$(tunnel_id)"
  if [[ -z "$id" ]]; then
    cloudflared tunnel create "$TUNNEL"
    id="$(tunnel_id)"
  fi
  [[ -n "$id" ]] || die "could not find tunnel $TUNNEL"
  creds="$HOME/.cloudflared/$id.json"
  # The credentials file only exists on the machine that created the tunnel; fetch it otherwise.
  [[ -f "$creds" ]] || cloudflared tunnel token --cred-file "$creds" "$TUNNEL" >/dev/null
  cat > "$HOME/.cloudflared/config.yml" <<EOF
# Written by deploy/start_hosting.sh
tunnel: $id
credentials-file: $creds
ingress:
  - hostname: $DOMAIN
    service: http://127.0.0.1:8000
  - hostname: www.$DOMAIN
    service: http://127.0.0.1:8000
  - service: http_status:404
EOF
  echo "tunnel id: $id"
  cloudflared tunnel route dns --overwrite-dns "$TUNNEL" "$DOMAIN"
  cloudflared tunnel route dns --overwrite-dns "$TUNNEL" "www.$DOMAIN"

  step "7/8 Tunnel service"
  install_tunnel_service

  step "8/8 Public check"
  local i live=0
  for i in $(seq 1 30); do
    if curl -fsS --max-time 5 "https://$DOMAIN/healthz" 2>/dev/null; then
      printf '\n\n\033[1;32mUniverse IO is live: https://%s\033[0m\n' "$DOMAIN"
      live=1; break
    fi
    sleep 2
  done
  [[ $live == 1 ]] || warn "https://$DOMAIN is not answering yet. Tunnel log: ~/Library/Logs/com.cloudflare.cloudflared.err.log"

  # Things this script can't change for you.
  pmset -g | grep -q 'autorestart *1' || warn "Turn on System Settings → Energy → 'Start up automatically after a power failure'."
  pmset -g | grep -Eq '^ *sleep *0' || warn "Turn on System Settings → Energy → 'Prevent automatic sleeping when the display is off'."
  [[ -n "$(defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser 2>/dev/null)" ]] ||
    warn "Turn on automatic login (System Settings → Users & Groups): both services only run while you are logged in."
  echo "Also once, in the Cloudflare dashboard: SSL/TLS → Edge Certificates → 'Always Use HTTPS' = on."
  echo "Server log: ~/Library/Logs/universe-io/server.log"
}

# Everything runs inside main so a `git pull` that rewrites this file mid-run can't break it.
main "$@"
