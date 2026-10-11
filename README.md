# Galaxy.io
A browser IO game about the universe. Start as a speck of dust, eat and grow, and climb the
astrophysical ladder: asteroid → planet → star → black hole → quasar → galaxy.

Authors: Jocelyn, TQ

## Run locally
```bash
conda activate galaxyio            # Python 3.11
pip install -r requirements-dev.txt
uvicorn server.main:app --reload --reload-dir server --port 8000
# open http://localhost:8000
```

Tests: `pytest server/tests`

Hosting it (Mac + Cloudflare Tunnel, galaxyio.fun): see `deploy/DEPLOY.md`.

The original 2022 pygame LAN version is in `legacy/`.
See `CLAUDE.md` for the design, decisions and roadmap.
