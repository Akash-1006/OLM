# routers/master_admin.py
"""
Master Admin API — secured by require_master_admin.

Base URL: /master/...

Endpoints:
  GET  /master/tenants             — list all tenants
  POST /master/tenants             — create a new tenant (auto-provisions defaults)
  GET  /master/tenants/{id}        — tenant detail
  PUT  /master/tenants/{id}        — update tenant (plan, status, branding, keys)
  POST /master/tenants/{id}/suspend— suspend tenant
  POST /master/tenants/{id}/activate— reactivate tenant
  GET  /master/stats               — platform-wide KPIs
  GET  /master/config/defaults     — platform defaults for new tenants
  POST /master/config/defaults     — update platform defaults
  POST /master/tenants/{id}/reset-key  — rotate miniapp access key
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from dependencies import get_db, require_master_admin
from models.tenant import Tenant
from models.tenant_config import TenantConfig, set_config
from models.lead import Lead


router = APIRouter(prefix="/master", tags=["master_admin"])


# ── Default config template applied to every new tenant ──────────────────────
DEFAULT_TENANT_CONFIG = {
    "stages":               ["Pile", "Footing", "Column", "Slab", "Beam", "Flooring", "Plaster"],
    "materials":            ["RMC", "TMT", "Blocks", "Sand", "Aggregate"],
    "work_statuses":        ["Just Started", "In Progress", "50% Done", "Nearly Complete", "Won", "Lost"],
    "default_monthly_leads":  30,
    "default_conversion_pct": 40.0,
    "default_volume_m3":      500.0,
}


def _provision_defaults(db: Session, tenant_id: int, overrides: dict = None):
    """Write default config rows for a newly created tenant."""
    config = {**DEFAULT_TENANT_CONFIG, **(overrides or {})}
    for key, value in config.items():
        set_config(db, tenant_id, key, value)


# ── Platform stats ──────────────────────────────────────────────────────────────

@router.get("/stats")
async def platform_stats(
    _: bool = Depends(require_master_admin),
    db: Session = Depends(get_db),
):
    total_tenants  = db.query(Tenant).count()
    active_tenants = db.query(Tenant).filter(Tenant.status == "active").count()
    total_leads    = db.query(Lead).count()
    leads_per_tenant = db.query(
        Lead.tenant_id, func.count(Lead.id).label("c")
    ).group_by(Lead.tenant_id).all()
    return {
        "total_tenants":  total_tenants,
        "active_tenants": active_tenants,
        "total_leads":    total_leads,
        "leads_per_tenant": [{"tenant_id": r.tenant_id, "count": r.c} for r in leads_per_tenant],
    }


# ── List tenants ─────────────────────────────────────────────────────────────────

@router.get("/tenants")
async def list_tenants(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    _: bool = Depends(require_master_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Tenant)
    if status:
        q = q.filter(Tenant.status == status)
    total   = q.count()
    tenants = q.order_by(Tenant.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page":  page,
        "tenants": [{
            "id":         t.id,
            "name":       t.name,
            "slug":       t.slug,
            "status":     t.status,
            "plan":       t.plan,
            "brand_name": t.brand_name,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        } for t in tenants],
    }


# ── Create tenant ──────────────────────────────────────────────────────────────

@router.post("/tenants", status_code=201)
async def create_tenant(
    request: Request,
    _: bool = Depends(require_master_admin),
    db: Session = Depends(get_db),
):
    """
    Body:
      name, slug, plan, admin_password, miniapp_access_key (optional),
      telegram_bot_token (optional), brand_name (optional),
      config_overrides (optional dict)
    """
    data = await request.json()

    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or "").strip().lower().replace(" ", "-")
    if not name or not slug:
        raise HTTPException(status_code=400, detail="name and slug are required")

    existing = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Slug '{slug}' already taken")

    tenant = Tenant(
        name=name,
        slug=slug,
        status="active",
        plan=data.get("plan", "starter"),
        admin_password_hash=data.get("admin_password", ""),
        miniapp_access_key=data.get("miniapp_access_key") or secrets.token_urlsafe(24),
        telegram_bot_token=data.get("telegram_bot_token"),
        brand_name=data.get("brand_name") or name,
        brand_color=data.get("brand_color"),
        miniapp_base_url=data.get("miniapp_base_url"),
        webhook_url=data.get("webhook_url"),
    )
    db.add(tenant)
    db.flush()   # get tenant.id without final commit

    # Provision default config
    _provision_defaults(db, tenant.id, data.get("config_overrides"))

    db.commit()
    db.refresh(tenant)

    return {
        "status":            "created",
        "tenant_id":         tenant.id,
        "slug":              tenant.slug,
        "miniapp_access_key": tenant.miniapp_access_key,
    }


# ── Get / update tenant ─────────────────────────────────────────────────────────────

@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: int,
    _: bool = Depends(require_master_admin),
    db: Session = Depends(get_db),
):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")

    lead_count = db.query(Lead).filter(Lead.tenant_id == tenant_id).count()
    configs    = db.query(TenantConfig).filter(TenantConfig.tenant_id == tenant_id).all()
    import json
    return {
        "id": t.id, "name": t.name, "slug": t.slug, "status": t.status, "plan": t.plan,
        "brand_name": t.brand_name, "brand_color": t.brand_color,
        "miniapp_base_url": t.miniapp_base_url, "webhook_url": t.webhook_url,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "lead_count": lead_count,
        "config": {c.key: json.loads(c.value_json) if c.value_json else None for c in configs},
    }


@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    request: Request,
    _: bool = Depends(require_master_admin),
    db: Session = Depends(get_db),
):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")

    data = await request.json()
    for field in [
        "name", "plan", "status", "brand_name", "brand_color",
        "miniapp_base_url", "webhook_url", "telegram_bot_token",
        "admin_password_hash", "miniapp_access_key",
    ]:
        if field in data:
            setattr(t, field, data[field])

    if "config" in data:
        for key, value in data["config"].items():
            set_config(db, tenant_id, key, value)

    db.commit()
    return {"status": "updated"}


# ── Suspend / activate ────────────────────────────────────────────────────────────────

@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: int,
    _: bool = Depends(require_master_admin),
    db: Session = Depends(get_db),
):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    t.status = "suspended"
    db.commit()
    return {"status": "suspended", "tenant_id": tenant_id}


@router.post("/tenants/{tenant_id}/activate")
async def activate_tenant(
    tenant_id: int,
    _: bool = Depends(require_master_admin),
    db: Session = Depends(get_db),
):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    t.status = "active"
    db.commit()
    return {"status": "activated", "tenant_id": tenant_id}


# ── Rotate miniapp access key ──────────────────────────────────────────────────────────

@router.post("/tenants/{tenant_id}/reset-key")
async def reset_miniapp_key(
    tenant_id: int,
    _: bool = Depends(require_master_admin),
    db: Session = Depends(get_db),
):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    new_key = secrets.token_urlsafe(32)
    t.miniapp_access_key = new_key
    db.commit()
    return {"status": "ok", "miniapp_access_key": new_key}


# ── Platform defaults (used when provisioning new tenants) ─────────────────────

@router.get("/config/defaults")
async def get_platform_defaults(_: bool = Depends(require_master_admin)):
    return DEFAULT_TENANT_CONFIG


@router.post("/config/defaults")
async def update_platform_defaults(
    request: Request,
    _: bool = Depends(require_master_admin),
):
    data = await request.json()
    DEFAULT_TENANT_CONFIG.update(data)
    return {"status": "ok", "defaults": DEFAULT_TENANT_CONFIG}
