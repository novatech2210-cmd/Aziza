"""
Qube Admin API — Auth
JWT-based admin authentication.
"""

from __future__ import annotations

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError  # type: ignore

import config

_bearer = HTTPBearer()


def verify_token_raw(token: str) -> dict | None:
    """Decode a raw JWT string. Returns payload or None on failure."""
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except JWTError:
        return None


def _decode_token(token: str) -> dict:
    payload = verify_token_raw(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


async def require_admin(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """FastAPI dependency — raises 403 unless token carries role='admin'."""
    payload = _decode_token(creds.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload
