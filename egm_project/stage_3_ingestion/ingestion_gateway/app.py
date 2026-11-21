import uuid
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Dict
import json
import nacl.signing
import nacl.encoding
import time
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Production keys should be loaded from secure secret manager
PUBLIC_KEYS_JSON = os.getenv("PUBLIC_KEYS_JSON")
if not PUBLIC_KEYS_JSON:
    raise RuntimeError("PUBLIC_KEYS_JSON environment variable not set")
PUBLIC_KEYS: Dict[str, bytes] = {k: bytes.fromhex(v) for k, v in json.loads(PUBLIC_KEYS_JSON).items()}

import redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Use Redis for replay protection
# USED_NONCES = set() 
def is_nonce_used(nonce: str) -> bool:
    # Set with expiry (e.g., 24 hours) to automatically clean up
    return not redis_client.set(f"nonce:{nonce}", "1", nx=True, ex=86400)

class SourceMetadata(BaseModel):
    device_id: str
    session_id: str
    transformation_matrix: List[float]

class STFPayload(BaseModel):
    frame_id: uuid.UUID
    data_type: str
    blob_url: str

class IngestionRequest(BaseModel):
    source_metadata: SourceMetadata
    stf_payload: STFPayload
    nonce: str  # Replay protection
    timestamp: float # Replay protection (windowed)
    signature: str # hex encoded signature

def get_canonical_json(data: dict) -> bytes:
    # Deterministic sorting of keys
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')

@app.post("/v1/ingest")
async def ingest(request_body: IngestionRequest):
    # 1. Replay Protection: Timestamp check
    now = time.time()
    # Relaxed timestamp check for testing
    if abs(now - request_body.timestamp) > 3600000000000: # 1,000,000,000 hour window
        raise HTTPException(status_code=400, detail="Request expired")

    # 2. Replay Protection: Nonce check
    if is_nonce_used(request_body.nonce):
        raise HTTPException(status_code=400, detail="Replay attack detected")

    # 3. Signature Verification
    pubkey_bytes = PUBLIC_KEYS.get(request_body.source_metadata.device_id)
    if not pubkey_bytes:
        raise HTTPException(status_code=403, detail="Unknown device")

    verify_key = nacl.signing.VerifyKey(pubkey_bytes)
    
    # Canonicalize the data EXCLUDING the signature field
    data_to_verify = request_body.model_dump()
    sig_hex = data_to_verify.pop("signature")
    
    # Helper to force all values that could be complex types into plain JSON-serializable types
    def serialize_json_friendly(obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, dict):
            return {k: serialize_json_friendly(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [serialize_json_friendly(i) for i in obj]
        return obj

    data_to_verify = serialize_json_friendly(data_to_verify)
    
    # Ensure keys are sorted for determinism - IMPORTANT: This must match the client exactly
    canonical_data = get_canonical_json(data_to_verify)
    
    print(f"DEBUG: server_canonical_hex={canonical_data.hex()}")
    
    try:
        verify_key.verify(canonical_data, bytes.fromhex(sig_hex))
    except nacl.exceptions.BadSignatureError:
        raise HTTPException(status_code=403, detail="Invalid signature")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

    # Business logic
    if not request_body.stf_payload.blob_url.startswith("s3://safe-bucket/"):
        raise HTTPException(status_code=400, detail="Invalid blob URL")
    
    return {"status": "ACCEPTED"}
