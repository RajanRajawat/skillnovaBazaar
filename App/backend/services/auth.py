from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException, Request

try:
    from ..config.settings import settings
    from ..models.user import User, user_store
except ImportError:
    from config.settings import settings
    from models.user import User, user_store


EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)


class AuthTokenError(Exception):
    pass


def normalize_name(value: str) -> str:
    clean = " ".join(str(value or "").strip().split())
    if len(clean) < 2:
        raise ValueError("Name must be at least 2 characters")
    return clean[:80]


def normalize_email(value: str) -> str:
    clean = str(value or "").strip().lower()
    if not EMAIL_PATTERN.fullmatch(clean):
        raise ValueError("Enter a valid email address")
    return clean


def validate_password(value: str) -> str:
    clean = str(value or "")
    if len(clean) < 8:
        raise ValueError("Password must be at least 8 characters")
    return clean


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def register_user(name: str, email: str, password: str) -> User:
    clean_name = normalize_name(name)
    clean_email = normalize_email(email)
    clean_password = validate_password(password)
    return user_store.create(clean_name, clean_email, hash_password(clean_password))


def authenticate_user(email: str, password: str) -> User:
    clean_email = normalize_email(email)
    clean_password = validate_password(password)
    user = user_store.find_by_email(clean_email)
    if not user or not verify_password(clean_password, user.password_hash):
        raise ValueError("Invalid email or password")
    return user


def reset_password(email: str, password: str, confirm_password: str) -> User:
    clean_email = normalize_email(email)
    clean_password = validate_password(password)
    clean_confirm_password = validate_password(confirm_password)
    if clean_password != clean_confirm_password:
        raise ValueError("Passwords do not match")
    user = user_store.update_password(clean_email, hash_password(clean_password))
    if not user:
        raise ValueError("No account found for this email")
    return user


def create_access_token(user: User) -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(hours=settings.jwt_expiration_hours)
    payload = {
        "sub": user.id,
        "email": user.email,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    if not settings.jwt_secret:
        raise AuthTokenError("JWT secret is not configured")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthTokenError("Session expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthTokenError("Invalid token") from exc
    if not payload.get("sub"):
        raise AuthTokenError("Invalid token")
    return payload


async def auth_middleware(request: Request, call_next: Any) -> Any:
    request.state.user = None
    request.state.auth_error = None

    header = str(request.headers.get("Authorization") or "").strip()
    if header:
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            request.state.auth_error = "Invalid authorization header"
        else:
            try:
                payload = decode_access_token(token.strip())
                user = user_store.find_by_id(str(payload["sub"]))
                if not user:
                    request.state.auth_error = "User not found"
                else:
                    request.state.user = user.to_public_dict()
            except AuthTokenError as exc:
                request.state.auth_error = str(exc)

    return await call_next(request)


def require_authenticated_user(request: Request) -> dict[str, str]:
    user = getattr(request.state, "user", None)
    if user:
        return user
    detail = getattr(request.state, "auth_error", None) or "Authentication required"
    raise HTTPException(status_code=401, detail=detail)
