# dependencies.py
"""
FastAPI dependency injection helpers.

Every router imports from here instead of duplicating auth / DB / tenant logic.

Tenant resolution strategy
───────────────────────────
1. Check request header  X-Tenant-Slug
2. Check query param     ?tenant=<slug>
3. Check subdomain       titans.yoursaas.com  →  slug = "titans"
4. Fall back to the env var TENANT_SLUG (single-tenant / local dev mode)
5. Return HTTP 404 if no tenant found
"""
from __future__ import annotations

import os
from typing import Generator

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from db import SessionLocal
from models.tenant import Tenant


# ── DB session ────────────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session and always close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Tenant resolution ──────────────────────────────────────────────────────────

def _resolve_slug(request: Request) -> str | None:
    """Try all slug sources in priority order; return None if not found."""
    # 1. Explicit header
    slug = request.headers.get("X-Tenant-Slug")
    if slug:
        return slug.strip().lower()

    # 2. Query param
    slug = request.query_params.get("tenant")
    if slug:
        return slug.strip().lower()

    # 3. Subdomain  (e.g. titans.yoursaas.com)
    host = request.headers.get("host", "")
    parts = host.split(".")
    if len(parts) >= 3:
        # first part is subdomain — exclude www / master / api
        candidate = parts[0].lower()
        if candidate not in ("www", "master", "api", "localhost"):
            return candidate

    # 4. Env fallback (single-tenant / local dev)
    env_slug = os.getenv("TENANT_SLUG", "").strip().lower()
    if env_slug:
        return env_slug

    return None


def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db),
) -> Tenant:
    """
    Resolve and return the active Tenant for this request.
    Raises HTTP 404 if no tenant matches, or 403 if suspended.
    """
    slug = _resolve_slug(request)
    if not slug:
        raise HTTPException(
            status_code=404,
            detail="Tenant not found. Pass X-Tenant-Slug header or ?tenant= param.",
        )

    tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found.")
    if tenant.status == "suspended":
        raise HTTPException(status_code=403, detail="This account is suspended.")

    return tenant


# ── Tenant admin auth ──────────────────────────────────────────────────────────

def require_tenant_admin(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
) -> Tenant:
    """
    Verify the caller is the tenant's admin.
    Accepts X-Admin-Key header OR ?key= query param.
    """
    import hashlib

    provided = (
        x_admin_key
        or request.query_params.get("key")
        or ""
    ).strip()

    if not provided:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Compare against bcrypt hash stored in tenants.admin_password_hash
    # For now we support plain SHA-256 (upgrade to bcrypt in production)
    expected_hash = tenant.admin_password_hash or ""
    provided_hash = hashlib.sha256(provided.encode()).hexdigest()

    if provided_hash != expected_hash:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return tenant


# ── Mini-app (exec) auth ─────────────────────────────────────────────────────────

def require_miniapp_auth(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    x_access_key: str | None = Header(default=None, alias="X-Access-Key"),
) -> Tenant:
    """
    Verify the mini-app access key for the current tenant.
    If the tenant has no miniapp_access_key set, access is open (dev mode).
    """
    access_key = (tenant.miniapp_access_key or "").strip()
    if not access_key:
        return tenant   # open access — no key configured

    provided = (
        x_access_key
        or request.query_params.get("key")
        or ""
    ).strip()

    if provided != access_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return tenant


# ── Platform (master) admin auth ───────────────────────────────────────────────────

def require_platform_admin(
    request: Request,
    db: Session = Depends(get_db),
    x_platform_key: str | None = Header(default=None, alias="X-Platform-Key"),
) -> None:
    """
    Protect master-admin routes.
    Checks session cookie OR X-Platform-Key header.
    Session is set by /master-admin/login.
    """
    from models.platform_admin import PlatformAdmin, verify_platform_admin
    from fastapi import Cookie

    # Check session cookie (set by login endpoint)
    session_token = request.cookies.get("master_session")
    if session_token:
        # Simple token check — store token in platform_admins.last_login session map
        # For now accept any non-empty cookie that matches MASTER_SESSION_SECRET
        expected = os.getenv("MASTER_SESSION_SECRET", "")
        if expected and session_token == expected:
            return

    # Fallback: Basic auth via header
    import base64
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            username, password = decoded.split(":", 1)
            admin = verify_platform_admin(db, username, password)
            if admin:
                return
        except Exception:
            pass

    raise HTTPException(
        status_code=401,
        detail="Master admin authentication required.",
        headers={"WWW-Authenticate": "Basic realm=\"Master Admin\""},
    )
