# NFC Video Backend (Cloudflare Worker)

This backend is fully refactored for Cloudflare Python Workers.

## Runtime model

- Entry point: `main.py` (`WorkerEntrypoint`)
- Persistent mapping storage: D1 (`env.DB`)
- Video storage: R2 (`env.VIDEO_BUCKET`)
- CDN auth: signed, short-lived media URLs (`/cdn/<key>?exp=...&sig=...`)
- Stream endpoint: validates business token, then redirects to authenticated CDN URL
- No SQLite usage
- No local `uvicorn` service

## Required bindings and vars

Configured in `wrangler.jsonc`:

- `d1_databases[0].binding = "DB"`
- `r2_buckets[0].binding = "VIDEO_BUCKET"`
- `vars.SDM_KEY_HEX` (NTAG SDM AES key)
- `vars.CDN_URL_TTL_SECONDS` (media signed URL valid time)
- Secret `TOKEN_SECRET` (business token signing)
- Secret `CDN_SIGN_SECRET` (CDN media URL signing, optional; defaults to `TOKEN_SECRET`)

Set secret:

```bash
uv run pywrangler secret put TOKEN_SECRET
uv run pywrangler secret put CDN_SIGN_SECRET
```

## D1 initialization

Create DB (first time) and execute schema:

```bash
uv run pywrangler d1 create nfc_video
uv run pywrangler d1 execute nfc_video --local --file db_init.sql
```

## R2 setup (video files stored on Cloudflare)

Create bucket and upload videos:

```bash
uv run pywrangler r2 bucket create nfc-video-assets
uv run pywrangler r2 object put nfc-video-assets/butterfly.mp4 --file ./butterfly.mp4
```

Then set `wrangler.jsonc`:

- `r2_buckets[0].bucket_name = "nfc-video-assets"`

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
- `GET /cdn/<object-key>?exp=<unix_ts>&sig=<signature>` (internal signed CDN endpoint)
- `GET /mappings`
