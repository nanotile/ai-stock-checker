"""JWT authentication helpers for the desk dashboard."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from fastapi import Request, Response
from fastapi.responses import RedirectResponse

from stock_checker.persistence import DataPersistence

# JWT settings
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24
JWT_COOKIE_NAME = "desk_token"

# Public paths that don't require auth
PUBLIC_PATHS = frozenset({
    "/desk/login",
    "/desk/auth/login",
    "/desk/static",
    "/favicon.ico",
    "/health",
    "/widgets.json",
    "/apps.json",
})


def _get_jwt_secret() -> str:
    """Read JWT secret from env or generate/persist one."""
    secret = os.getenv("JWT_SECRET")
    if secret:
        return secret

    data_dir = Path(os.getenv("DATA_DIR", "data"))
    secret_file = data_dir / "jwt_secret.txt"
    if secret_file.exists():
        return secret_file.read_text().strip()

    # Generate and persist
    data_dir.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(48)
    secret_file.write_text(secret)
    return secret


@lru_cache(maxsize=1)
def get_jwt_secret() -> str:
    return _get_jwt_secret()


def create_token(user_id: int, username: str) -> str:
    """Create a JWT token for a user."""
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def get_current_user(request: Request) -> Optional[dict]:
    """Extract current user from JWT cookie. Returns None if not authenticated."""
    token = request.cookies.get(JWT_COOKIE_NAME)
    if not token:
        return None
    return decode_token(token)


def set_auth_cookie(response: Response, token: str) -> None:
    """Set the JWT auth cookie on a response."""
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=JWT_EXPIRY_HOURS * 3600,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear the JWT auth cookie."""
    response.delete_cookie(key=JWT_COOKIE_NAME, path="/")


def requires_auth(request: Request) -> bool:
    """Check if a request path requires authentication.

    Auth is controlled by DESK_AUTH_ENABLED env var (default: false).
    Set DESK_AUTH_ENABLED=true to enforce JWT authentication.
    """
    path = request.url.path
    # Public paths
    for pub in PUBLIC_PATHS:
        if path == pub or path.startswith(pub + "/"):
            return False
    # OpenBB API endpoints use API key auth, not JWT
    if not path.startswith("/desk"):
        return False

    # Only enforce auth if explicitly enabled
    auth_enabled = os.getenv("DESK_AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
    if not auth_enabled:
        return False

    return True
