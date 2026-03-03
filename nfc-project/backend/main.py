import base64
import binascii
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, quote, unquote, urlparse

from js import Response as JsResponse
from js import Uint8Array, crypto
from pyodide.ffi import to_js
from workers import WorkerEntrypoint

DEFAULT_FILENAME = "butterfly.mp4"
DEFAULT_SDM_KEY_HEX = "518945027BB77671C3980890A13668E5"
TOKEN_TTL_SECONDS = 300
CDN_URL_TTL_SECONDS = 120
MEDIA_CACHE_SECONDS = 3600


def _json_response(payload: dict | list, status: int = 200):
    return JsResponse.new(
        json.dumps(payload),
        to_js(
            {
                "status": status,
                "headers": {
                    "content-type": "application/json; charset=utf-8",
                    "cache-control": "no-store",
                },
            }
        ),
    )


def _text_response(message: str, status: int = 200):
    return JsResponse.new(
        message,
        to_js(
            {
                "status": status,
                "headers": {
                    "content-type": "text/plain; charset=utf-8",
                    "cache-control": "no-store",
                },
            }
        ),
    )


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _js_to_py(value):
    if hasattr(value, "to_py"):
        return value.to_py()
    return value


def _field(row, key: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _safe_object_key(path_value: str) -> str:
    key = unquote(path_value).lstrip("/")
    if not key or "\x00" in key or "\n" in key or "\r" in key:
        raise ValueError("invalid object key")
    if ".." in key:
        raise ValueError("invalid object key")
    return key


def _normalize_media_key(raw_filename: str) -> str:
    filename = str(raw_filename or "").strip()
    if filename.startswith("http://") or filename.startswith("https://"):
        filename = urlparse(filename).path
    return _safe_object_key(filename)


async def _decrypt_sun_payload(p_hex: str, key: bytes) -> bytes:
    encrypted = binascii.unhexlify(p_hex)
    if not encrypted or len(encrypted) % 16 != 0:
        raise ValueError("Invalid p payload length")

    key_u8 = Uint8Array.new(len(key))
    for index, value in enumerate(key):
        key_u8[index] = value

    enc_u8 = Uint8Array.new(len(encrypted))
    for index, value in enumerate(encrypted):
        enc_u8[index] = value

    iv_u8 = Uint8Array.new(16)
    crypto_key = await crypto.subtle.importKey(
        "raw",
        key_u8,
        to_js({"name": "AES-CBC"}),
        False,
        to_js(["decrypt"]),
    )
    decrypted_buffer = await crypto.subtle.decrypt(
        to_js({"name": "AES-CBC", "iv": iv_u8}),
        crypto_key,
        enc_u8,
    )
    decrypted_u8 = Uint8Array.new(decrypted_buffer)
    try:
        return bytes(decrypted_u8.to_py())
    except Exception:
        return bytes(int(decrypted_u8[i]) for i in range(decrypted_u8.length))


class Default(WorkerEntrypoint):
    def _token_secret(self) -> bytes:
        secret = getattr(self.env, "TOKEN_SECRET", None)
        if not secret:
            # Development fallback. Set TOKEN_SECRET in production.
            secret = "dev-token-secret-change-me"
        return str(secret).encode("utf-8")

    def _cdn_secret(self) -> bytes:
        secret = getattr(self.env, "CDN_SIGN_SECRET", None)
        if secret:
            return str(secret).encode("utf-8")
        return self._token_secret()

    def _sign(self, payload: bytes) -> bytes:
        return hmac.new(self._token_secret(), payload, hashlib.sha256).digest()

    def _cdn_ttl_seconds(self) -> int:
        raw_value = getattr(self.env, "CDN_URL_TTL_SECONDS", CDN_URL_TTL_SECONDS)
        try:
            ttl = int(str(raw_value))
        except Exception:
            ttl = CDN_URL_TTL_SECONDS
        return max(30, min(ttl, 3600))

    def _cdn_signature(self, object_key: str, expires_at: int) -> str:
        payload = f"{object_key}\n{expires_at}".encode("utf-8")
        signature = hmac.new(self._cdn_secret(), payload, hashlib.sha256).digest()
        return _b64url_encode(signature)

    def _issue_cdn_url(self, origin: str, object_key: str) -> str:
        expires_at = int(time.time()) + self._cdn_ttl_seconds()
        signature = self._cdn_signature(object_key, expires_at)
        encoded_key = quote(object_key, safe="/")
        return f"{origin}/cdn/{encoded_key}?exp={expires_at}&sig={signature}"

    def _validate_cdn_url(self, object_key: str, exp_raw: str, sig_raw: str) -> bool:
        try:
            expires_at = int(exp_raw)
        except Exception:
            return False

        if int(time.time()) > expires_at:
            return False

        expected = self._cdn_signature(object_key, expires_at)
        return hmac.compare_digest(sig_raw, expected)

    def _issue_token(self, uid: str, filename: str) -> str:
        payload = {
            "uid": uid,
            "filename": filename,
            "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        }
        payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        signature = self._sign(payload_raw)
        return f"{_b64url_encode(payload_raw)}.{_b64url_encode(signature)}"

    def _validate_token(self, token: str) -> dict | None:
        try:
            payload_part, signature_part = token.split(".", 1)
            payload_raw = _b64url_decode(payload_part)
            signature_raw = _b64url_decode(signature_part)
        except Exception:
            return None

        expected_sig = self._sign(payload_raw)
        if not hmac.compare_digest(signature_raw, expected_sig):
            return None

        try:
            payload = json.loads(payload_raw.decode("utf-8"))
        except Exception:
            return None

        expires_at = int(payload.get("exp", 0))
        if int(time.time()) > expires_at:
            return None
        return payload

    async def _ensure_schema(self):
        if getattr(self, "_schema_ready", False):
            return
        await self.env.DB.prepare(
            """
            CREATE TABLE IF NOT EXISTS mappings (
                uid TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                name TEXT,
                updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
            """
        ).run()
        self._schema_ready = True

    async def _upsert_mapping(self, uid: str, filename: str, name: str | None) -> dict:
        uid_normalized = uid.upper()
        await self.env.DB.prepare(
            """
            INSERT INTO mappings (uid, filename, name, updated_at)
            VALUES (?, ?, ?, strftime('%s', 'now'))
            ON CONFLICT(uid) DO UPDATE SET
                filename = excluded.filename,
                name = excluded.name,
                updated_at = strftime('%s', 'now')
            """
        ).bind(uid_normalized, filename, name).run()
        return {"uid": uid_normalized, "filename": filename, "name": name}

    async def _get_mapping(self, uid: str) -> dict | None:
        uid_normalized = uid.upper()
        result = (
            await self.env.DB.prepare(
                "SELECT uid, filename, name FROM mappings WHERE uid = ? LIMIT 1"
            )
            .bind(uid_normalized)
            .all()
        )
        rows = _js_to_py(result.results)
        if not rows:
            return None
        row = rows[0]
        return {
            "uid": str(_field(row, "uid", uid_normalized)).upper(),
            "filename": str(_field(row, "filename", DEFAULT_FILENAME)),
            "name": _field(row, "name"),
        }

    async def _list_mappings(self) -> list[dict]:
        result = await self.env.DB.prepare(
            "SELECT uid, filename, name FROM mappings ORDER BY updated_at DESC"
        ).all()
        rows = _js_to_py(result.results) or []
        mappings: list[dict] = []
        for row in rows:
            mappings.append(
                {
                    "uid": str(_field(row, "uid", "")).upper(),
                    "filename": str(_field(row, "filename", DEFAULT_FILENAME)),
                    "name": _field(row, "name"),
                }
            )
        return mappings

    async def _handle_map(self, request):
        try:
            body = await request.text()
            payload = json.loads(body) if body else {}
        except Exception:
            return _json_response({"error": "Invalid JSON body"}, status=400)

        uid = str(payload.get("uid", "")).strip().upper()
        filename = str(payload.get("filename", "")).strip()
        name = payload.get("name")
        if name is not None:
            name = str(name)

        if not uid or not filename:
            return _json_response({"error": "uid and filename are required"}, status=400)

        mapping = await self._upsert_mapping(uid, filename, name)
        return _json_response(mapping)

    async def _handle_verify(self, request):
        parsed_url = urlparse(str(request.url))
        params = parse_qs(parsed_url.query)
        p = params.get("p", [None])[0]
        m = params.get("m", [None])[0]
        if not p or not m:
            return _json_response(
                {"success": False, "error": "Missing p or m parameters"},
                status=400,
            )

        sdm_key_hex = str(getattr(self.env, "SDM_KEY_HEX", DEFAULT_SDM_KEY_HEX)).strip()
        try:
            sdm_key = binascii.unhexlify(sdm_key_hex)
            if len(sdm_key) != 16:
                raise ValueError("SDM key must be 16 bytes (32 hex chars)")

            decrypted = await _decrypt_sun_payload(p, sdm_key)
            if len(decrypted) < 7:
                raise ValueError("Decrypted payload too short")
            uid_hex = binascii.hexlify(decrypted[0:7]).decode("utf-8").upper()

            # Keep m required for protocol compatibility.
            mapping = await self._get_mapping(uid_hex)
            if not mapping:
                mapping = await self._upsert_mapping(
                    uid_hex,
                    DEFAULT_FILENAME,
                    f"Secure Card {uid_hex[-4:]}",
                )

            token = self._issue_token(uid_hex, mapping["filename"])
            origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
            stream_url = f"{origin}/stream?token={token}"
            return _json_response(
                {
                    "success": True,
                    "video_url": stream_url,
                    "uid": uid_hex,
                }
            )
        except Exception:
            return _json_response(
                {"success": False, "error": "Invalid Signature or Key"},
                status=400,
            )

    async def _handle_stream(self, request):
        parsed_url = urlparse(str(request.url))
        params = parse_qs(parsed_url.query)
        token = params.get("token", [None])[0]
        if not token:
            return _json_response({"error": "Missing token"}, status=400)

        token_payload = self._validate_token(token)
        if not token_payload:
            return _json_response({"error": "Invalid or expired token"}, status=403)

        filename = str(token_payload.get("filename", "")).strip()
        if not filename:
            return _json_response({"error": "Invalid token payload"}, status=403)

        try:
            media_key = _normalize_media_key(filename)
            origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
            video_url = self._issue_cdn_url(origin, media_key)
        except Exception:
            return _json_response(
                {"error": "Invalid media key in token"},
                status=403,
            )

        return JsResponse.new(
            "",
            to_js(
                {
                    "status": 302,
                    "headers": {
                        "location": video_url,
                        "cache-control": "no-store",
                    },
                }
            ),
        )

    async def _handle_cdn_media(self, request, object_path: str):
        try:
            object_key = _safe_object_key(object_path)
        except Exception:
            return _json_response({"error": "Invalid media path"}, status=400)

        parsed_url = urlparse(str(request.url))
        params = parse_qs(parsed_url.query)
        exp = params.get("exp", [None])[0]
        sig = params.get("sig", [None])[0]
        if not exp or not sig:
            return _json_response({"error": "Missing media signature"}, status=403)

        if not self._validate_cdn_url(object_key, str(exp), str(sig)):
            return _json_response({"error": "Invalid or expired media signature"}, status=403)

        bucket = getattr(self.env, "VIDEO_BUCKET", None)
        if not bucket:
            return _json_response({"error": "VIDEO_BUCKET binding is missing"}, status=500)

        range_header = request.headers.get("range")
        r2_object = None
        if range_header:
            try:
                r2_object = await bucket.get(
                    object_key,
                    to_js({"range": str(range_header)}),
                )
            except Exception:
                r2_object = await bucket.get(object_key)
        else:
            r2_object = await bucket.get(object_key)

        if not r2_object:
            return _json_response({"error": "Video not found"}, status=404)

        headers = {
            "cache-control": f"public, max-age=0, s-maxage={MEDIA_CACHE_SECONDS}",
            "accept-ranges": "bytes",
        }

        metadata = getattr(r2_object, "httpMetadata", None)
        content_type = getattr(metadata, "contentType", None) if metadata else None
        headers["content-type"] = str(content_type or "video/mp4")

        etag = getattr(r2_object, "httpEtag", None)
        if etag:
            headers["etag"] = str(etag)

        status = 200
        size = getattr(r2_object, "size", None)
        if size is not None:
            try:
                headers["content-length"] = str(int(size))
            except Exception:
                pass

        range_info = getattr(r2_object, "range", None)
        if range_header and range_info is not None:
            try:
                start = int(getattr(range_info, "offset"))
                length = int(getattr(range_info, "length"))
                total = int(size) if size is not None else start + length
                end = start + length - 1
                headers["content-range"] = f"bytes {start}-{end}/{total}"
                headers["content-length"] = str(length)
                status = 206
            except Exception:
                pass

        if str(request.method).upper() == "HEAD":
            return JsResponse.new(
                "",
                to_js(
                    {
                        "status": status,
                        "headers": headers,
                    }
                ),
            )

        return JsResponse.new(
            r2_object.body,
            to_js(
                {
                    "status": status,
                    "headers": headers,
                }
            ),
        )

    async def fetch(self, request):
        method = str(request.method).upper()
        parsed_url = urlparse(str(request.url))
        path = parsed_url.path or "/"

        if path == "/health":
            return _json_response({"ok": True, "runtime": "cloudflare-worker-python"})

        if path == "/map":
            if method != "POST":
                return _text_response("Method Not Allowed", status=405)
            await self._ensure_schema()
            return await self._handle_map(request)

        if path == "/verify":
            if method != "GET":
                return _text_response("Method Not Allowed", status=405)
            await self._ensure_schema()
            return await self._handle_verify(request)

        if path == "/stream":
            if method != "GET":
                return _text_response("Method Not Allowed", status=405)
            return await self._handle_stream(request)

        if path.startswith("/cdn/"):
            if method not in ("GET", "HEAD"):
                return _text_response("Method Not Allowed", status=405)
            object_path = path[len("/cdn/") :]
            return await self._handle_cdn_media(request, object_path)

        if path == "/mappings":
            if method != "GET":
                return _text_response("Method Not Allowed", status=405)
            await self._ensure_schema()
            mappings = await self._list_mappings()
            return _json_response(mappings)

        return _text_response("Not Found", status=404)
