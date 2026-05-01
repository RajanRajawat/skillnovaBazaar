from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

try:
    from ..services.auth import (
        authenticate_user,
        create_access_token,
        register_user,
        require_authenticated_user,
        reset_password,
    )
except ImportError:
    from services.auth import (
        authenticate_user,
        create_access_token,
        register_user,
        require_authenticated_user,
        reset_password,
    )


router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""


class LoginRequest(BaseModel):
    email: str = ""
    password: str = ""


class ResetPasswordRequest(BaseModel):
    email: str = ""
    password: str = ""
    confirmPassword: str = ""


@router.post("/register")
def register(payload: RegisterRequest) -> dict[str, Any]:
    try:
        user = register_user(payload.name, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "token": create_access_token(user),
        "tokenType": "bearer",
        "user": user.to_public_dict(),
    }


@router.post("/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    try:
        user = authenticate_user(payload.email, payload.password)
    except ValueError as exc:
        message = str(exc)
        status_code = 401 if message == "Invalid email or password" else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {
        "token": create_access_token(user),
        "tokenType": "bearer",
        "user": user.to_public_dict(),
    }


@router.post("/reset-password")
def reset_password_route(payload: ResetPasswordRequest) -> dict[str, str]:
    try:
        reset_password(payload.email, payload.password, payload.confirmPassword)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == "No account found for this email" else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {"message": "Password reset successful"}


@router.get("/me")
def me(user: dict[str, str] = Depends(require_authenticated_user)) -> dict[str, Any]:
    return {"user": user}
