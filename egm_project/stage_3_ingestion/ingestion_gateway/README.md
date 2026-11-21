# Secret and Key Management Instructions

## 1. Public Key Provisioning
The gateway expects the Ed25519 public key of the client device to verify signatures.
- Store public keys in a secure management system (e.g., HashiCorp Vault, AWS Secrets Manager, or a hardened DB).
- Load these at runtime into the `PUBLIC_KEYS` dictionary.
- The example uses a simple dictionary based on `device_id`.

## 2. Environment Variables
- `DEVICE_PUBKEY_HEX`: The hex-encoded 32-byte Ed25519 public key for `trusted-device-01`.

## 3. Production Hardening
- **Storage:** Replace `USED_NONCES` (a Python set) with a distributed, TTL-based cache like Redis to ensure persistence across gateway restarts and horizontally scaled instances.
- **Clock Skew:** Ensure server clocks are synchronized via NTP; the 300s window is aggressive and may need tuning based on client distribution.
- **Key Rotation:** Implement a mechanism to fetch keys from the source of truth if a `device_id` is not found locally.
- **Canonicalization:** While `json.dumps(sort_keys=True)` is used, ensure the client-side serialization logic matches *exactly* (including whitespace handling). For higher standards, consider JCS (RFC 8785) if extreme cross-language compatibility is required.
