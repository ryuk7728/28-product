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
- A dedicated `game28-product-api` Cloud Run service hosts the API and room WebSockets.
- The container compiles and requires the Rust extension.
- Cloud Run must remain at one instance while room/game state is in memory.
- `VITE_API_BASE_URL` and `VITE_WS_BASE_URL` point at the product Cloud Run URL.

The legacy 28 Superhuman deployments are separate and must not be modified.
