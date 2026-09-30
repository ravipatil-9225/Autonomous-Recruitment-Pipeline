"""
Security Core: JWT + AES-256-GCM PII Encryption
─────────────────────────────────────────────────
• JWT access/refresh token creation and verification
• AES-256-GCM encrypt/decrypt for PII columns (name, email, phone)
• Password hashing via bcrypt (passlib)
"""

import base64
import hashlib
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import jwt

from backend.app.config import settings

# ── Password hashing ──────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Return bcrypt hash of a plaintext password."""
    pwd_bytes = plain.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext against stored bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ───────────────────────────────────────────────────────────────────────


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    """Create a long-lived JWT refresh token."""
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.
    Raises jose.JWTError on invalid/expired token.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


# ── PII Encryption (AES-256-GCM) ──────────────────────────────────────────────


def _get_aes_key() -> bytes:
    """Decode the base64-encoded AES-256 key from settings."""
    return base64.b64decode(settings.pii_encryption_key)


def encrypt_pii(plaintext: str) -> str:
    """
    Encrypt a PII string with AES-256-GCM.
    Returns base64(nonce + ciphertext + tag) as a string safe for DB storage.
    """
    key = _get_aes_key()
    nonce = os.urandom(12)  # 96-bit nonce (GCM standard)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
    # Prepend nonce so we can decrypt later: nonce(12) + ciphertext+tag
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_pii(encrypted: str) -> str:
    """
    Decrypt an AES-256-GCM encrypted PII string.
    Raises ValueError if the ciphertext is tampered.
    """
    key = _get_aes_key()
    raw = base64.b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, associated_data=None).decode("utf-8")


def hash_email(email: str) -> str:
    """
    SHA-256 hash of lowercased email for deduplication lookups.
    Never stored in plain; only used for indexed equality checks.
    """
    return hashlib.sha256(email.lower().encode("utf-8")).hexdigest()
