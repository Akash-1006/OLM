# dependencies.py
"""
FastAPI dependency injection helpers.

Used in every router via Depends():
    db      = Depends(get_db)
    tenant  = Depends(get_current_tenant)
    _       = Depends(require_tenant_admin)
    _       = Depends(require_master_admin)
"""
from fastapi import Depends, HTTPException, Header, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
from db import SessionLocal
from models.tenant import Tenant
from models.platform_admin import verify_platform_admin
import os


# ── Database session ──────────────────────────────────────────────────────────

def get_db():
    """Yield a SQLAlchemy session, close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Tenant resolution ─────────────────────────────────────────────────────────

def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db),
) -> Tenant:
    """
    Resolve the current tenant from the request.

    Resolution order:
      1. X-Tenant-ID header           (master admin impersonation / API calls)
      2. ?tenant_id= query param      (explicit API calls)
      3. Subdomain (host header)      e.g. "titans.yourdomain.com" → slug="titans"
      4. Single-tenant fallback       if only one tenant exists (backwards compat)

    Raises 404 if no tenant can be resolved.
    """
    tenant_id = request.headers.get("X-Tenant-ID") or request.query_params.get("tenant_id")

    if tenant_id:
        tenant = db.query(Tenant).filter(
            Tenant.id == int(tenant_id),
            Tenant.status == "active",
        ).first()
        if tenant:
            return tenant

    # Try subdomain
    host = request.headers.get("host", "")
    subdomain = host.split(".")[0] if "." in host else None
    if subdomain and subdomain not in ("www", "api", "admin"):
        tenant = db.query(Tenant).filter(
            Tenant.slug == subdomain,
            Tenant.status == "active",
        ).first()
        if tenant:
            return tenant

    # Single-tenant fallback (backwards compat for existing deployments)
    tenants = db.query(Tenant).filter(Tenant.status == "active").all()
    if len(tenants) == 1:
        return tenants[0]

    raise HTTPException(status_code=404, detail="Tenant not found")


# ── Auth: Tenant Admin ────────────────────────────────────────────────────────

def require_tenant_admin(
    request: Request,
    x_admin_key: Optional[str] = Header(default=None),
    key: Optional[str] = Query(default=None),
    tenant: Tenant = Depends(get_current_tenant),
) -> Tenant:
    """
    Validate the tenant admin password.
    Accepts key via X-Admin-Key header OR ?key= query param.
    Falls back to ADMIN_PASSWORD env var if tenant has no password set.
    """
    provided_key = x_admin_key or key or ""
    expected_key = tenant.admin_password_hash or os.getenv("ADMIN_PASSWORD", "")

    if not expected_key or provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return tenant


# ── Auth: Miniapp Access ──────────────────────────────────────────────────────

def require_app_auth(
    request: Request,
    x_access_key: Optional[str] = Header(default=None),
    key: Optional[str] = Query(default=None),
    tenant: Tenant = Depends(get_current_tenant),
) -> Tenant:
    """
    Validate the miniapp access key for a tenant.
    Falls back to MINIAPP_ACCESS_KEY env var.
    """
    provided_key = x_access_key or key or ""
    expected_key = tenant.miniapp_access_key or os.getenv("MINIAPP_ACCESS_KEY", "")

    # If no key configured at all, allow (open access — legacy behaviour)
    if not expected_key:
        return tenant

    if provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return tenant


# ── Auth: Master Admin ────────────────────────────────────────────────────────

def require_master_admin(
    request: Request,
    x_admin_key: Optional[str] = Header(default=None),
    key: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Validate master admin credentials.
    Accepts key via X-Master-Key header OR ?key= query param.
    The key must match MASTER_ADMIN_PASSWORD env var.
    """
    provided_key = request.headers.get("X-Master-Key") or x_admin_key or key or ""
    master_key   = os.getenv("MASTER_ADMIN_PASSWORD", "")

    if not master_key or provided_key != master_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return True
