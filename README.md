# Twenty-Eight

A touch-first multiplayer Twenty-Eight product for one to four people. Empty seats are filled by the Rust-powered AI from 28 Superhuman, with a fixed production policy and no exposed technical settings.

Read [PRODUCT_SPEC.md](./PRODUCT_SPEC.md) for the full interaction, room, bot, accessibility, test, and deployment contract.

## Local development

Backend (PowerShell):

```powershell
cd backend
$env:APP_MINIMAX_BACKEND='rust'
$env:APP_MINIMAX_STRICT_RUST='1'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Frontend:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 4173
```

Open `http://127.0.0.1:4173`.

## Checks

```powershell
python -m pytest backend/tests/test_multiplayer_rooms.py -q
cd frontend
npm run build
```

## Production architecture

- Vercel serves `frontend/`.
- The dedicated Linux game host runs the API and room WebSockets as the
  `28-product.service` user service.
- Tailscale Funnel exposes that loopback-only API over public HTTPS/WSS.
- The Python 3.10 virtual environment contains a release build of the Rust
  extension, and strict-Rust startup refuses to serve if that extension fails.
- The current four-core host uses four rollout workers and serializes bot turns
  so simultaneous searches cannot overload it.
- `VITE_API_BASE_URL` and `VITE_WS_BASE_URL` point at the product Funnel URL.

The checked-in service and environment templates live in `deploy/linux/`.

The legacy 28 Superhuman deployments are separate and must not be modified.
