"""Sign in.

Viva: only the three emails in security.py are accepted.
activate creates the account on the first visit. login is every visit after that.
The password is checked by Supabase Auth. This file does not store passwords itself.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from supabase import create_client

from config import get_settings
from database import supabase_admin, supabase_public
from security import is_allowed_email, normalize_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class ActivateRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""


def _reject_unknown(email: str) -> str:
    cleaned = normalize_email(email)
    if not is_allowed_email(cleaned):
        raise HTTPException(
            status_code=403,
            detail="This email is not one of the three accounts allowed to use Student Management System.",
        )
    return cleaned


def _session_payload(response, full_name: str = ""):
    metadata = response.user.user_metadata or {}
    return {
        "user": {
            "id": response.user.id,
            "email": response.user.email,
            "full_name": metadata.get("full_name") or full_name,
        },
        "session": {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_in": response.session.expires_in,
        },
    }


def _sign_in(email: str, password: str):
    """Sign in on a fresh client so one login cannot overwrite another session."""
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_publishable_key)
    return client.auth.sign_in_with_password({"email": email, "password": password})


@router.post("/login")
async def login(body: LoginRequest):
    """Sign in with email and password. Unknown emails are refused."""
    email = _reject_unknown(body.email)
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Enter the password for this account.")
    try:
        response = _sign_in(email, body.password)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Password was not accepted. If this is the first time for this email, set a password instead of signing in.",
        )
    if not response.session or not response.user:
        raise HTTPException(status_code=401, detail="Sign-in did not return a session.")
    return _session_payload(response)


@router.post("/activate")
async def activate(body: ActivateRequest):
    """Create one of the three approved accounts and sign in. Existing accounts are left as they are."""
    email = _reject_unknown(body.email)
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Choose a password of at least 8 characters.")
    try:
        supabase_admin.auth.admin.create_user(
            {
                "email": email,
                "password": body.password,
                "email_confirm": True,
                "user_metadata": {"full_name": body.full_name or email.split("@")[0]},
            }
        )
    except Exception as exc:
        message = str(exc).lower()
        if "already" in message or "registered" in message or "exists" in message:
            raise HTTPException(
                status_code=409,
                detail="This account already has a password. Sign in with it.",
            )
        raise HTTPException(status_code=400, detail=f"Could not create the account: {exc}")

    try:
        response = _sign_in(email, body.password)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Account was created, but sign-in failed: {exc}",
        )
    return _session_payload(response, body.full_name)


@router.post("/verify-password")
async def verify_password(body: LoginRequest, authorization: Optional[str] = Header(None)):
    """Re-check the signed-in user's password before a database change."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Sign in required")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    try:
        current = supabase_public.auth.get_user(token).user
    except Exception:
        raise HTTPException(status_code=401, detail="Session expired. Sign in again.")
    current_email = normalize_email(current.email or "")
    if not is_allowed_email(current_email):
        raise HTTPException(status_code=403, detail="This account is not allowed.")
    if normalize_email(body.email) != current_email:
        raise HTTPException(status_code=403, detail="Enter the password for the account you are signed in with.")
    try:
        _sign_in(current_email, body.password)
    except Exception:
        raise HTTPException(status_code=401, detail="Password did not match. The change was not applied.")
    return {"ok": True, "email": current_email}


@router.get("/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Return the user associated with the bearer token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is required")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    try:
        user = supabase_public.auth.get_user(token).user
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {exc}")
    email = normalize_email(user.email or "")
    if not is_allowed_email(email):
        raise HTTPException(status_code=403, detail="This account is not allowed.")
    return {
        "id": user.id,
        "email": user.email,
        "full_name": (user.user_metadata or {}).get("full_name", ""),
        "created_at": str(user.created_at) if user.created_at else None,
    }
