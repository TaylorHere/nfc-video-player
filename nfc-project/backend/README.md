# NFC Video Backend (Cloudflare Worker)

Cloudflare-native backend for:

1. NFC verify link (`/verify?p=...&m=...`)
2. Access-controlled playback session generation
3. CDN delivery via Worker + R2
4. DRM-friendly playback flow (HLS/DASH manifest + license proxy)

---

## End-to-end flow (production)

1. **NFC URL** hits `/verify`
2. Worker decrypts SUN payload, finds UID mapping in D1
3. Worker issues short-lived **business token**
4. Client calls `/stream?token=...`
5. Worker validates token and:
   - non-DRM: redirects to signed `/cdn/...`
   - DRM: issues playback session token and redirects to signed `/play/<session>/<manifest>`
6. Player loads manifest/segments through `/play/...` (CDN path + access control)
7. Player requests license via `/license/<session>/<drm-system>` (proxy)

---

## Runtime model

- Entry: `main.py` (`WorkerEntrypoint`)
- Metadata: D1 (`env.DB`)
- Media objects: R2 (`env.VIDEO_BUCKET`)
- Access control:
  - Business token: `/stream?token=...`
  - CDN signed URL: `/cdn/<key>?exp=...&sig=...`
  - DRM playback session token: `/play/<session>/<object>`

---

## Required bindings and vars

In `wrangler.jsonc`:

- `d1_databases[0].binding = "DB"`
- `r2_buckets[0].binding = "VIDEO_BUCKET"`
- `vars.SDM_KEY_HEX`
- `vars.TOKEN_TTL_SECONDS`
- `vars.CDN_URL_TTL_SECONDS`
- `vars.PLAYBACK_SESSION_TTL_SECONDS`
- Optional default DRM license URLs:
  - `vars.DRM_WIDEVINE_LICENSE_URL`
  - `vars.DRM_FAIRPLAY_LICENSE_URL`
  - `vars.DRM_PLAYREADY_LICENSE_URL`
- Optional default DRM certificate URLs:
  - `vars.DRM_WIDEVINE_CERTIFICATE_URL`
  - `vars.DRM_FAIRPLAY_CERTIFICATE_URL`
  - `vars.DRM_PLAYREADY_CERTIFICATE_URL`
- Optional default DRM license headers (JSON string):
  - `vars.DRM_WIDEVINE_LICENSE_HEADERS_JSON`
  - `vars.DRM_FAIRPLAY_LICENSE_HEADERS_JSON`
  - `vars.DRM_PLAYREADY_LICENSE_HEADERS_JSON`

Secrets:

- `TOKEN_SECRET` (required)
- `CDN_SIGN_SECRET` (optional, default `TOKEN_SECRET`)
- `PLAYBACK_SIGN_SECRET` (optional, default `CDN_SIGN_SECRET`)
- `DRM_LICENSE_AUTHORIZATION` (optional static auth header for upstream DRM provider)

```bash
uv run pywrangler secret put TOKEN_SECRET
uv run pywrangler secret put CDN_SIGN_SECRET
uv run pywrangler secret put PLAYBACK_SIGN_SECRET
uv run pywrangler secret put DRM_LICENSE_AUTHORIZATION
```

---

## D1 setup

```bash
uv run pywrangler d1 create nfc_video
uv run pywrangler d1 execute nfc_video --local --file db_init.sql
```

---

## R2 setup

```bash
uv run pywrangler r2 bucket create nfc-video-assets
uv run pywrangler r2 object put nfc-video-assets/demo/master.m3u8 --file ./master.m3u8
uv run pywrangler r2 object put nfc-video-assets/demo/seg-0001.m4s --file ./seg-0001.m4s
```

Then set:

- `r2_buckets[0].bucket_name = "nfc-video-assets"`

---

## Mapping API (`/map`) examples

### Non-DRM mapping

```json
{
  "uid": "04999911223344",
  "filename": "promo/butterfly.mp4",
  "name": "Promo Card"
}
```

### DRM mapping (recommended)

```json
{
  "uid": "04999911223344",
  "filename": "demo/master.m3u8",
  "name": "DRM Card",
  "drm": {
    "enabled": true,
    "hls_manifest": "demo/master.m3u8",
    "dash_manifest": "demo/manifest.mpd",
    "licenses": {
      "widevine": "https://license.example.com/widevine",
      "fairplay": "https://license.example.com/fairplay",
      "playready": "https://license.example.com/playready"
    },
    "certificates": {
      "fairplay": "https://license.example.com/fairplay.cer"
    },
    "headers": {
      "widevine": {
        "x-drm-client": "nfc-app"
      },
      "fairplay": {
        "x-drm-client": "nfc-app-ios"
      }
    }
  }
}
```

---

## API summary

- `GET /health`
- `POST /map`
- `GET /verify?p=<hex>&m=<hex>`
- `GET /stream?token=<signed-token>`
- `GET /stream?token=<signed-token>&mode=json` (returns playback descriptor JSON)
- `GET|HEAD /cdn/<object-key>?exp=<unix_ts>&sig=<signature>`
- `GET|HEAD /play/<session-token>/<object-key>` (DRM-friendly CDN path)
- `POST|GET|HEAD|OPTIONS /license/<session-token>/<widevine|fairplay|playready>`
- `GET|HEAD|OPTIONS /certificate/<session-token>/<widevine|fairplay|playready>`
- `GET /mappings`

---

## Dev / Deploy

```bash
uv run pywrangler dev
uv run pywrangler deploy
```

---

## Notes for DRM packaging

- Use encrypted HLS/DASH with relative segment paths where possible.
- HLS supports replacing `__FAIRPLAY_LICENSE_URL__` placeholder at runtime via Worker.
- HLS also supports `__FAIRPLAY_CERTIFICATE_URL__` placeholder if your packager template uses it.
- Access control is enforced on every `/play/...` segment request via session token.
