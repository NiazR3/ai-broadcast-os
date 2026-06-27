"""
Authentication API — signup, login, logout, profile.

All endpoints are public.  JWT-based sessions managed via Supabase Auth
with Bearer token in the Authorization header for authenticated requests.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from backend.services.user_service import (
    is_configured,
    signup,
    login,
    verify_token,
    sign_out,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Schemas ──


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user: dict | None = None
    session: dict | None = None
    error: str | None = None


# ── Endpoints ──


@router.get("/status")
async def auth_status():
    """Check whether the auth backend is configured."""
    return {"configured": is_configured()}


@router.post("/signup", response_model=AuthResponse)
async def api_signup(body: SignupRequest):
    """Create a new account.  Returns user + session on success."""
    if not is_configured():
        raise HTTPException(
            status_code=501,
            detail="Auth service not configured — set SUPABASE_URL and SUPABASE_SERVICE_KEY",
        )

    result = signup(body.email, body.password)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return AuthResponse(
        user=result.get("user"),
        session=result.get("session"),
    )


@router.post("/login", response_model=AuthResponse)
async def api_login(body: LoginRequest):
    """Authenticate with email + password.  Returns user + session."""
    if not is_configured():
        raise HTTPException(
            status_code=501,
            detail="Auth service not configured",
        )

    result = login(body.email, body.password)
    if result.get("error"):
        raise HTTPException(status_code=401, detail=result["error"])

    return AuthResponse(
        user=result.get("user"),
        session=result.get("session"),
    )


@router.post("/logout")
async def api_logout(request: Request):
    """Revoke the current session."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="No auth token")

    result = sign_out(token)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return {"success": True}


@router.get("/me")
async def api_me(request: Request):
    """Return the current user's profile from the Bearer token."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="No auth token")

    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {"user": user}


@router.post("/verify")
async def api_verify(request: Request):
    """Verify a Bearer token and return user info."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="No auth token")

    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {"valid": True, "user": user}


# ── Helpers ──


def _extract_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None
