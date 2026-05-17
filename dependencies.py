# dependencies.py
"""
FastAPI dependency functions shared across all routers.

Usage in a route:
    @router.get("/some-route")
    def my_route(
        db: Session = Depends(get_db),
        _: None = Depends(require_admin),
    ):
        ...
"""
from fastapi import Depends, Header, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from db import get_db
from config import ADMIN_PASSWORD, MINIAPP_ACCESS_KEY, MASTER_ADMIN_KEY


# ── Tenant-admin auth (X-Admin-Key header or ?key= query param) ───────────────

def require_admin(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    key: Optional[str] = Query(None),
):
    """
    Protects /admin/* routes.
    Accepts the key via:
      - X-Admin-Key request header
      - ?key= query param
    """
    provided = x_admin_key or key or ""
    if provided != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Mini-app auth (X-Access-Key header or ?key= query param) ─────────────────

def require_app_auth(
    x_access_key: Optional[str] = Header(None, alias="X-Access-Key"),
    key: Optional[str] = Query(None),
):
    """
    Protects /submit_lead, /generate_quote, and /api/* miniapp routes.
    If MINIAPP_ACCESS_KEY is not set, all requests are allowed (legacy mode).
    """
    if not MINIAPP_ACCESS_KEY:
        return  # open access — no key configured
    provided = x_access_key or key or ""
    if provided != MINIAPP_ACCESS_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Master-admin auth (platform super-admin) ──────────────────────────────────

def require_master_admin(
    x_master_key: Optional[str] = Header(None, alias="X-Master-Key"),
    key: Optional[str] = Query(None),
):
    """
    Protects /master-admin/* routes.
    Set MASTER_ADMIN_KEY in .env to enable.
    """
    if not MASTER_ADMIN_KEY:
        raise HTTPException(
            status_code=503,
            detail="Master admin not configured. Set MASTER_ADMIN_KEY in .env."
        )
    provided = x_master_key or key or ""
    if provided != MASTER_ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
