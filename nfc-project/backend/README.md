# NFC Video Backend (Cloudflare Worker)

This backend is fully refactored for Cloudflare Python Workers.

## Runtime model

- Entry point: `main.py` (`WorkerEntrypoint`)
- Persistent mapping storage: D1 (`env.DB`)
- Stream endpoint: signed token + HTTP redirect to asset host
- No local filesystem usage
- No SQLite usage
- No local `uvicorn` service

## Required bindings and vars

Configured in `wrangler.jsonc`:

- `d1_databases[0].binding = "DB"`
- `vars.ASSET_BASE_URL` (for relative filenames)
- `vars.SDM_KEY_HEX` (NTAG SDM AES key)
- Secret `TOKEN_SECRET` (recommended)

Set secret:

```bash
uv run pywrangler secret put TOKEN_SECRET
```

## D1 initialization

Create DB (first time) and execute schema:

```bash
uv run pywrangler d1 create nfc_video
uv run pywrangler d1 execute nfc_video --local --file db_init.sql
```

## Run locally

```bash
uv run pywrangler dev
```

## Deploy

```bash
uv run pywrangler deploy
```

## API summary

- `GET /health`
- `POST /map` body: `{ "uid": "...", "filename": "...", "name": "..." }`
- `GET /verify?p=<hex>&m=<hex>`
- `GET /stream?token=<signed-token>`
- `GET /mappings`
