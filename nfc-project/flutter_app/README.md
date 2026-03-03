# Flutter NFC Secure Player

Flutter client for the Cloudflare Worker backend flow:

1. NFC read URL from NTAG
2. Call backend `/verify?p=...&m=...`
3. Call `/stream?token=...&mode=json` to get playback descriptor
4. Play:
   - non-DRM file URL
   - DRM stream (Widevine on Android / FairPlay on iOS) via Better Player

## Dependencies

- `nfc_manager`
- `http`
- `better_player`

## Run

```bash
flutter pub get
flutter run
```

## Important config

Edit `lib/main.dart` and set:

```dart
const _defaultBackendBaseUrl = 'https://<your-worker-domain>.workers.dev';
```

This fallback is used when NFC URL is not directly pointing to `/verify` on your Worker domain.

## NFC URL expectation

App treats URL as secure verify link when query contains both:

- `p`
- `m`

Example:

```text
https://deo.app/nfc?p=<hex>&m=<hex>
```

## DRM expectation

The backend should return playback descriptor in `/stream?mode=json`:

- `type` (`drm` or `file`)
- `default_url`, `hls_url`, `dash_url`
- `licenses.widevine`, `licenses.fairplay`, `licenses.playready`

Android uses Widevine when available, iOS uses FairPlay when available.
