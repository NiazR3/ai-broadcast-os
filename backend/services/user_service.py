"""
Supabase user management service.
Handles signup, login, token verification, and user profile lookups.
"""

from __future__ import annotations

import logging
from typing import Optional

from supabase import create_client, Client

from backend import config

logger = logging.getLogger("prod_dash")

_supabase: Optional[Client] = None


def _get_admin_client() -> Optional[Client]:
    """Lazy-init Supabase admin client (service_role key)."""
    global _supabase
    if _supabase is None and config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
        try:
            _supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
        except Exception as exc:
            logger.warning("Supabase admin client init failed: %s", exc)
            _supabase = None  # will retry on next call
    return _supabase


def is_configured() -> bool:
    """True when Supabase credentials are set."""
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)


# ── Public helpers ──


def signup(email: str, password: str) -> dict:
    """
    Create a new user via Supabase Auth.
    Returns dict with 'user', 'session', or 'error'.
    """
    client = _get_admin_client()
    if not client:
        return {"error": "Auth service not configured"}

    try:
        resp = client.auth.sign_up({"email": email, "password": password})
        return {
            "user": resp.user.model_dump(mode="json") if resp.user else None,
            "session": resp.session.model_dump(mode="json") if resp.session else None,
        }
    except Exception as exc:
        msg = str(exc)
        logger.info("Signup failed for %s: %s", email, msg)
        return {"error": msg}


def login(email: str, password: str) -> dict:
    """
    Authenticate a user with email + password.
    Returns dict with 'user', 'session', or 'error'.
    """
    client = _get_admin_client()
    if not client:
        return {"error": "Auth service not configured"}

    try:
        resp = client.auth.sign_in_with_password({"email": email, "password": password})
        return {
            "user": resp.user.model_dump(mode="json") if resp.user else None,
            "session": resp.session.model_dump(mode="json") if resp.session else None,
        }
    except Exception as exc:
        msg = str(exc)
        logger.info("Login failed for %s: %s", email, msg)
        return {"error": msg}


def verify_token(access_token: str) -> Optional[dict]:
    """
    Verify a JWT access token against Supabase.
    Returns the user dict or None.
    """
    client = _get_admin_client()
    if not client:
        return None

    try:
        resp = client.auth.get_user(access_token)
        if resp and resp.user:
            return resp.user.model_dump(mode="json")
        return None
    except Exception as exc:
        logger.debug("Token verification failed: %s", exc)
        return None


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch a user's profile by ID via admin API."""
    client = _get_admin_client()
    if not client:
        return None

    try:
        resp = client.auth.admin.get_user_by_id(user_id)
        if resp and resp.user:
            return resp.user.model_dump(mode="json")
        return None
    except Exception as exc:
        logger.debug("Admin get_user failed: %s", exc)
        return None


def sign_out(access_token: str) -> dict:
    """Revoke a session."""
    client = _get_admin_client()
    if not client:
        return {"error": "Auth service not configured"}

    try:
        client.auth.admin.sign_out(access_token)
        return {"success": True}
    except Exception as exc:
        return {"error": str(exc)}
