# Hosting Galaxy.io on a Mac (galaxyio.fun)

The game is one Python process listening on `127.0.0.1:8000`. A **Cloudflare Tunnel**
(`cloudflared`) makes an outgoing connection to Cloudflare, and Cloudflare serves
`https://galaxyio.fun` (HTTPS + WebSockets) through it. Why a tunnel:

- no router port-forwarding, and your home IP address stays hidden
- HTTPS certificates are automatic
- Cloudflare absorbs junk traffic before it reaches your Mac
- free

```
kid's browser ──https/wss──▶ Cloudflare ◀──tunnel── cloudflared ──▶ 127.0.0.1:8000 (Galaxy.io)
                                                     └──────── your Mac Studio ────────┘
```

## 0. Try it without a domain (2 minutes)

```bash
scripts/run_prod.sh                                   # terminal 1 (set GALAXY_PYTHON if needed)
cloudflared tunnel --url http://127.0.0.1:8000        # terminal 2: prints https://<random>.trycloudflare.com
```

The random URL works from any phone or computer until you stop `cloudflared`.

## 1. One-time Mac Studio setup

1. **Keep it awake.** System Settings → Energy: turn on *Prevent automatic sleeping when the display
   is off* and *Start up automatically after a power failure*. Optionally turn on automatic login
   (Users & Groups) so the services start after a reboot without anyone logging in.
2. **Get the code and Python 3.11:**
   ```bash
   git clone git@github.com:Jocelynzhang/Galaxy.io.git ~/Galaxy.io && cd ~/Galaxy.io
   conda create -n galaxyio -c conda-forge python=3.11 pip      # or: python3.11 -m venv .venv
   conda activate galaxyio && pip install -r requirements.txt
   ```
3. **Install the game server as a background service** (starts at login, restarts if it stops):
   ```bash
   deploy/install_mac_service.sh "$(which python)" "https://galaxyio.fun,https://www.galaxyio.fun"
   ```
   It prints the `/healthz` result when it's up. Logs: `~/Library/Logs/galaxyio/server.log`.

## 2. Domain + tunnel (once)

1. **Buy `galaxyio.fun`** at any registrar (Cloudflare Registrar, Porkbun, Namecheap…).
2. **Add it to Cloudflare** (free plan): dash.cloudflare.com → *Add a domain*. If you bought it
   elsewhere, change the registrar's nameservers to the two Cloudflare gives you. Wait until
   Cloudflare says the domain is *Active*.
3. **Install cloudflared:** `brew install cloudflared`, or download `cloudflared-darwin-arm64.tgz`
   from https://github.com/cloudflare/cloudflared/releases.
4. **Create the tunnel:**
   ```bash
   cloudflared tunnel login                       # opens a browser: pick galaxyio.fun
   cloudflared tunnel create galaxyio             # prints the tunnel ID, writes ~/.cloudflared/<ID>.json
   cp deploy/cloudflared-config.example.yml ~/.cloudflared/config.yml   # then fill in <TUNNEL-ID> and <you>
   cloudflared tunnel route dns galaxyio galaxyio.fun
   cloudflared tunnel route dns galaxyio www.galaxyio.fun
   cloudflared tunnel run galaxyio                # test: open https://galaxyio.fun
   ```
5. **Run the tunnel as a service** (Ctrl+C the test run first):
   ```bash
   cloudflared service install                    # LaunchAgent that reads ~/.cloudflared/config.yml
   ```
6. Optional, in the Cloudflare dashboard: SSL/TLS → Edge Certificates → *Always Use HTTPS* = on.

## 3. Day to day

| Task | Command |
|---|---|
| Is it up? | `curl https://galaxyio.fun/healthz` → `{"ok":true, "humans":…, "tick_ms":…}` |
| Update to the latest code | `cd ~/Galaxy.io && git pull && launchctl kickstart -k gui/$(id -u)/fun.galaxyio.server` |
| Restart the server | `launchctl kickstart -k gui/$(id -u)/fun.galaxyio.server` |
| Stop the server | `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/fun.galaxyio.server.plist` |
| Server logs | `tail -f ~/Library/Logs/galaxyio/server.log` |

## Built-in safeguards (server/game/config.py)

- Listens only on `127.0.0.1`; the tunnel is the only way in.
- At most 8 connections per visitor IP (real IP read from Cloudflare's `CF-Connecting-IP`), 300 total.
- At most 40 human players; extra visitors watch the game and get a "universe is full" message.
- Per-connection message rate limit (connections that flood get closed), 4 KB max message,
  a 1-second join cooldown, and an Origin check so other websites can't connect to the game.
- Player names pass a profanity filter; there is no chat; nothing about players is stored.
- An exception in one game tick is logged and the game keeps running (`errors` in `/healthz`).
