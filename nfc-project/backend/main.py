from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import os
import binascii
import secrets
import time
from Crypto.Cipher import AES

# Video Storage Path (Not accessible via static serving)
VIDEO_STORAGE_PATH = "secure_videos"
VIDEO_STORAGE_AVAILABLE = True
try:
    os.makedirs(VIDEO_STORAGE_PATH, exist_ok=True)
except OSError:
    # Cloudflare Worker runtime has no persistent local filesystem.
    VIDEO_STORAGE_AVAILABLE = False

# Access Token Store (In-memory for simplicity, use Redis in production)
# Structure: { token: {"uid": uid, "expiry": timestamp} }
access_tokens = {}

# Schemas
class MappingCreate(BaseModel):
    uid: str
    filename: str
    name: str = None

class MappingResponse(BaseModel):
    uid: str
    filename: str
    name: str = None

class SunVerifyRequest(BaseModel):
    sun_data: str

# App
app = FastAPI(title="NFC Secure Video Streamer")

# Mapping store
# Cloudflare Worker has no sqlite module, so use in-memory mapping.
mapping_store: dict[str, MappingResponse] = {}


def upsert_mapping(uid: str, filename: str, name: str | None) -> MappingResponse:
    normalized_uid = uid.upper()
    mapping = MappingResponse(uid=normalized_uid, filename=filename, name=name)
    mapping_store[normalized_uid] = mapping
    return mapping


def get_mapping(uid: str) -> MappingResponse | None:
    return mapping_store.get(uid.upper())

# SDM Key
SDM_KEY_HEX = "518945027BB77671C3980890A13668E5"
SDM_KEY = binascii.unhexlify(SDM_KEY_HEX)

def decrypt_sun_message(p_hex: str, m_hex: str, key: bytes):
    try:
        enc_data = binascii.unhexlify(p_hex)
        iv = bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(enc_data)
        return decrypted
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")

@app.post("/map", response_model=MappingResponse)
def create_mapping(mapping: MappingCreate):
    return upsert_mapping(mapping.uid, mapping.filename, mapping.name)

@app.get("/verify")
def verify_sun(request: Request, p: str = None, m: str = None):
    """
    Verifies SUN message and returns a temporary access token for video streaming.
    """
    if not p or not m:
        return {"success": False, "error": "Missing p or m parameters"}
        
    try:
        # 1. Verify / Decrypt
        decrypted = decrypt_sun_message(p, m, SDM_KEY)
        
        # 2. Extract UID
        uid_bytes = decrypted[0:7]
        uid_hex = binascii.hexlify(uid_bytes).decode('utf-8').upper()
        
        print(f"Verified SUN Message. Real UID: {uid_hex}")
        
        # 3. Lookup Content
        mapping = get_mapping(uid_hex)
        
        if not mapping:
            # Auto-register default content if new card
            # Using a sample file name, make sure this file exists in VIDEO_STORAGE_PATH
            default_filename = "butterfly.mp4" 
            mapping = upsert_mapping(
                uid_hex,
                default_filename,
                f"Secure Card {uid_hex[-4:]}",
            )

        # 4. Generate Temporary Access Token
        token = secrets.token_urlsafe(32)
        access_tokens[token] = {
            "uid": uid_hex,
            "filename": mapping.filename if mapping else "butterfly.mp4",
            "expiry": time.time() + 300 # Valid for 5 minutes
        }
        
        # Construct the streaming URL with the token
        # request.base_url automatically gets the correct scheme/host/port
        stream_url = f"{request.base_url}stream?token={token}"

        return {"success": True, "video_url": stream_url, "uid": uid_hex}
        
    except Exception as e:
        print(f"Verify Error: {e}")
        return {"success": False, "error": "Invalid Signature or Key"}

def range_stream_response(file_obj, start, end, file_size):
    """Generator for streaming file chunks"""
    chunk_size = 1024 * 1024 # 1MB chunks
    file_obj.seek(start)
    remaining = end - start + 1
    
    while remaining > 0:
        read_size = min(chunk_size, remaining)
        data = file_obj.read(read_size)
        if not data:
            break
        remaining -= len(data)
        yield data

@app.get("/stream")
def stream_video(token: str, request: Request):
    """
    Secure video streaming endpoint. Only works with valid token.
    Supports HTTP Range requests for seeking.
    """
    # 1. Validate Token
    if token not in access_tokens:
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    
    token_data = access_tokens[token]
    if time.time() > token_data["expiry"]:
        del access_tokens[token]
        raise HTTPException(status_code=403, detail="Token expired")
        
    if not VIDEO_STORAGE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Video storage unavailable in current runtime",
        )

    filename = token_data["filename"]
    file_path = os.path.join(VIDEO_STORAGE_PATH, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file not found on server")

    file_size = os.path.getsize(file_path)
    
    # 2. Handle Range Header
    range_header = request.headers.get("range")
    
    if range_header:
        # Parse "bytes=0-1024"
        try:
            start_str, end_str = range_header.replace("bytes=", "").split("-")
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
        except ValueError:
            start = 0
            end = file_size - 1
            
        if start >= file_size:
             raise HTTPException(status_code=416, detail="Range not satisfiable")
             
        content_length = end - start + 1
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": "video/mp4",
        }
        
        return StreamingResponse(
            range_stream_response(open(file_path, "rb"), start, end, file_size),
            status_code=206,
            headers=headers,
            media_type="video/mp4"
        )
    else:
        # Full file
        return StreamingResponse(
            open(file_path, "rb"),
            media_type="video/mp4"
        )

@app.get("/mappings", response_model=list[MappingResponse])
def list_mappings():
    return list(mapping_store.values())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
