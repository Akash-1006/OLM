# routers/miniapp.py
"""
Mini-app routes (Telegram WebApp):
  GET  /miniapp                  – serve the HTML
  GET  /miniapp/update           – serve HTML in update mode
  POST /submit_lead              – save a new lead
  POST /generate_quote           – generate & send PDF quote
  POST /api/auth                 – validate miniapp access key
  GET  /api/lead/<id>            – get lead for update form
  POST /api/lead/<id>/update     – update existing lead
  GET  /api/stats                – exec stats summary
  GET  /api/goals                – exec monthly goals vs targets
  GET  /api/history              – exec lead history
  GET  /api/tenant-config        – config-driven dropdowns for this tenant
"""
from __future__ import annotations

import io
import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from db import SessionLocal
from dependencies import get_db, get_current_tenant, require_miniapp_auth
from models.lead import Lead
from models.lead_update import LeadUpdate
from models.exec_target import ExecTarget
from models.tenant import Tenant
from models.tenant_config import get_config

router = APIRouter()

_IST = timezone(timedelta(hours=5, minutes=30))
_IST_OFFSET = timedelta(hours=5, minutes=30)


def _to_ist_str(dt: datetime | None) -> str | None:
    if not dt:
        return None
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return (aware + _IST_OFFSET).strftime("%Y-%m-%dT%H:%M")


def _is_overdue(l: Lead) -> bool:
    if l.site_status in ("Won", "Lost") or not l.last_followup_at:
        return False
    if l.last_user_update_at and l.last_user_update_at >= l.last_followup_at:
        return False
    lfa_ist = l.last_followup_at.replace(tzinfo=timezone.utc).astimezone(_IST)
    deadline = lfa_ist.replace(hour=18, minute=30, second=0, microsecond=0)
    return datetime.now(timezone.utc).astimezone(_IST) > deadline


# ── Serve mini-app HTML ───────────────────────────────────────────────────────────

def _serve_miniapp_html(tenant: Tenant) -> HTMLResponse:
    base_url = (tenant.miniapp_base_url or tenant.webhook_url or "").rstrip("/")
    path = os.path.join("miniapp", "index.html")
    with open(path, "r") as fh:
        html = fh.read()
    html = html.replace("https://YOUR_NGROK_OR_DOMAIN", base_url)
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/miniapp", response_class=HTMLResponse)
async def serve_miniapp(tenant: Tenant = Depends(get_current_tenant)):
    return _serve_miniapp_html(tenant)


@router.get("/miniapp/update", response_class=HTMLResponse)
async def serve_miniapp_update(tenant: Tenant = Depends(get_current_tenant)):
    return _serve_miniapp_html(tenant)


# ── Tenant config endpoint (drives all dropdowns in the mini-app) ───────────────────

@router.get("/api/tenant-config")
async def get_tenant_config(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Return all config-driven UI options for this tenant."""
    stages         = get_config(db, tenant.id, "stages",         ["Foundation", "Brick", "Plastering", "Ready"])
    materials      = get_config(db, tenant.id, "materials",      ["White", "Colour", "Aluminium"])
    work_statuses  = get_config(db, tenant.id, "work_statuses",  ["Visited", "Quoted", "Won", "Lost"])
    followup_rules = get_config(db, tenant.id, "followup_rules", {})
    brand_name     = get_config(db, tenant.id, "brand_name",     tenant.name)
    digest_time    = get_config(db, tenant.id, "digest_time_ist", "20:00")

    return {
        "tenant_id":      tenant.id,
        "brand_name":     brand_name,
        "stages":         stages,
        "materials":      materials,
        "work_statuses":  work_statuses,
        "followup_rules": followup_rules,
        "digest_time_ist": digest_time,
    }


# ── Auth ────────────────────────────────────────────────────────────────────────

@router.post("/api/auth")
async def api_auth(request: Request, tenant: Tenant = Depends(get_current_tenant)):
    data = await request.json()
    key  = (data.get("key") or "").strip()
    access_key = (tenant.miniapp_access_key or "").strip()
    if not access_key or key == access_key:
        return {"status": "ok"}
    raise HTTPException(status_code=401, detail="Invalid access key")


# ── Submit lead ───────────────────────────────────────────────────────────────────

@router.post("/submit_lead")
async def submit_lead(
    request: Request,
    tenant: Tenant = Depends(require_miniapp_auth),
    db: Session = Depends(get_db),
):
    form = await request.form()
    telegram_app = request.app.state.telegram_app

    company_name = (form.get("company_name") or "").strip()
    contact_name = (form.get("contact_name") or "").strip()
    phone        = (form.get("phone")        or "").strip()
    work_status  = (form.get("work_status")  or "").strip()
    stage        = (form.get("stage")        or "").strip()
    material     = (form.get("material")     or "").strip()
    grade        = (form.get("grade")        or "").strip()
    quantity     = (form.get("quantity")     or "").strip()
    remarks      = (form.get("remarks")      or "").strip()
    nfd_str      = (form.get("next_followup_date") or "").strip()

    # Parse follow-up datetime (IST naive → UTC)
    next_followup_date = None
    if nfd_str:
        try:
            next_followup_date = datetime.fromisoformat(nfd_str) - _IST_OFFSET
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid next_followup_date format.")

    try:
        latitude  = float(form.get("latitude"))  if form.get("latitude")  else None
        longitude = float(form.get("longitude")) if form.get("longitude") else None
    except (ValueError, TypeError):
        latitude = longitude = None

    try:
        tg_user = json.loads(form.get("tg_user") or "{}")
    except Exception:
        tg_user = {}

    chat_id   = tg_user.get("id")
    user_name = (
        tg_user.get("name")
        or " ".join(filter(None, [tg_user.get("first_name", ""), tg_user.get("last_name", "")]))
        or tg_user.get("username")
        or "Unknown"
    )

    missing = [k for k, v in {
        "company_name": company_name, "contact_name": contact_name,
        "phone": phone, "work_status": work_status,
        "stage": stage, "material": material,
        "quantity": quantity, "next_followup_date": nfd_str,
    }.items() if not v]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing)}")
    if not latitude or not longitude:
        raise HTTPException(status_code=400, detail="Location is required")

    # Save uploaded photos
    UPLOAD_DIR = os.path.join("uploads", "leads")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    photo_paths = []
    for key in form.multi_items():
        field_name, field_value = key
        if field_name.startswith("photo_") and hasattr(field_value, "filename") and field_value.filename:
            safe = f"{chat_id or 'unknown'}_{field_name}_{field_value.filename}"
            save_path = os.path.join(UPLOAD_DIR, safe)
            content = await field_value.read()
            with open(save_path, "wb") as f_out:
                f_out.write(content)
            photo_paths.append(save_path)

    if not photo_paths:
        raise HTTPException(status_code=400, detail="At least one photo is required")

    try:
        lead = Lead(
            tenant_id=tenant.id,
            company_name=company_name,
            client_name=contact_name,
            client_phone=phone,
            site_status=work_status,
            stage=stage,
            material=material,
            grade=grade,
            quantity=quantity,
            remarks=remarks,
            photo_paths=",".join(photo_paths),
            latitude=latitude,
            longitude=longitude,
            location=f"{latitude:.5f},{longitude:.5f}",
            sales_exec_id=chat_id,
            sales_exec_name=user_name,
            next_followup_date=next_followup_date,
            last_user_update_at=datetime.utcnow(),
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")

    # Schedule follow-up reminder
    if chat_id:
        from bot.scheduler import schedule_followups
        schedule_followups(
            lead_id=lead.id,
            chat_id=chat_id,
            bot=telegram_app.bot,
            loop=request.app.state.bot_loop,
            stage=stage,
        )

    print(f"✅ Lead #{lead.id} saved — {company_name} | {stage} | {material} [tenant={tenant.slug}]")
    return {"status": "ok", "lead_id": lead.id}


# ── Generate quote PDF ───────────────────────────────────────────────────────────

@router.post("/generate_quote")
async def generate_quote(
    request: Request,
    tenant: Tenant = Depends(require_miniapp_auth),
):
    telegram_app = request.app.state.telegram_app
    data = await request.json()

    company  = (data.get("company_name") or "").strip()
    quantity = (data.get("quantity")     or "").strip()
    grade    = (data.get("grade")        or "").strip()
    rate     = (data.get("rate")         or "").strip()
    location = (data.get("location")     or "").strip()

    try:
        tg_user = json.loads(data.get("tg_user") or "{}") \
                  if isinstance(data.get("tg_user"), str) else (data.get("tg_user") or {})
    except Exception:
        tg_user = {}

    chat_id   = tg_user.get("id") or data.get("user_id")
    exec_name = (
        " ".join(filter(None, [tg_user.get("first_name", ""), tg_user.get("last_name", "")]))
        or tg_user.get("username") or "Executive"
    ).strip()

    if not all([company, quantity, grade, rate, location, chat_id]):
        raise HTTPException(status_code=400, detail="Missing required fields")

    # Tenant-specific quote template: static/<tenant_slug>/quote_template.pdf
    # Fall back to shared static/quote_template.pdf
    template_dir = os.getenv("QUOTE_TEMPLATE_DIR", "static")
    tenant_template = os.path.join(template_dir, tenant.slug, "quote_template.pdf")
    shared_template = os.path.join(template_dir, "quote_template.pdf")
    template_path   = tenant_template if os.path.exists(tenant_template) else shared_template

    if not os.path.exists(template_path):
        raise HTTPException(status_code=500, detail=f"Quote template not found at '{template_path}'.")

    from bot.quote_generator import build_quote_pdf
    buf = io.BytesIO()
    try:
        build_quote_pdf(
            out_buf=buf, template_path=template_path,
            company=company, location=location,
            quantity=quantity, grade=grade, rate=rate, exec_name=exec_name,
        )
        buf.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    now_ist  = datetime.now(_IST)
    date_str = now_ist.strftime("%d %b %Y")
    brand    = tenant.name.replace(" ", "_")
    filename = f"{brand}_Quote_{company.replace(' ', '_')}_{date_str.replace(' ', '')}.pdf"

    try:
        qty_f  = float(quantity)
    except (ValueError, TypeError):
        qty_f  = 0.0
    try:
        rate_f = float(rate)
    except (ValueError, TypeError):
        rate_f = 0.0

    await telegram_app.bot.send_document(
        chat_id=int(chat_id),
        document=buf,
        filename=filename,
        caption=(
            f"📄 *Quote — {company}*\n"
            f"📍 {location}  |  🏗 {grade}  |  📦 {qty_f:.0f} cum\n"
            f"💰 Rate: \u20b9{rate_f:,.0f}/cum (incl. GST)"
        ),
        parse_mode="Markdown",
    )

    print(f"📄 Quote sent to {chat_id} — {company} | {grade} | {qty_f:.0f} cum [tenant={tenant.slug}]")
    return {"status": "ok", "filename": filename}


# ── Lead detail (for update form pre-fill) ─────────────────────────────────────────

@router.get("/api/lead/{lead_id}")
async def api_lead_detail(
    lead_id: int,
    user_id: int,
    tenant: Tenant = Depends(require_miniapp_auth),
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.tenant_id == tenant.id,
        Lead.sales_exec_id == user_id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return {
        "id":           lead.id,
        "company_name": lead.company_name,
        "client_name":  lead.client_name,
        "client_phone": lead.client_phone,
        "site_status":  lead.site_status,
        "stage":        lead.stage,
        "material":     lead.material,
        "grade":        lead.grade,
        "quantity":     lead.quantity,
        "remarks":      lead.remarks,
        "latitude":     lead.latitude,
        "longitude":    lead.longitude,
        "next_followup_date": _to_ist_str(lead.next_followup_date),
    }


# ── Update existing lead ────────────────────────────────────────────────────────────

@router.post("/api/lead/{lead_id}/update")
async def api_update_lead(
    lead_id: int,
    request: Request,
    tenant: Tenant = Depends(require_miniapp_auth),
    db: Session = Depends(get_db),
):
    telegram_app = request.app.state.telegram_app
    form = await request.form()

    try:
        tg_user   = json.loads(form.get("tg_user") or "{}")
        user_id   = tg_user.get("id")
        user_name = (
            tg_user.get("name")
            or " ".join(filter(None, [tg_user.get("first_name", ""), tg_user.get("last_name", "")]))
            or tg_user.get("username") or "Unknown"
        )
    except Exception:
        user_id = user_name = None

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.tenant_id == tenant.id,
        Lead.sales_exec_id == user_id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Apply field updates
    for field, attr in [
        ("company_name", "company_name"), ("contact_name", "client_name"),
        ("phone", "client_phone"), ("work_status", "site_status"),
        ("stage", "stage"), ("material", "material"),
        ("grade", "grade"), ("quantity", "quantity"), ("remarks", "remarks"),
    ]:
        v = (form.get(field) or "").strip()
        if v:
            setattr(lead, attr, v)

    lead.last_user_update_at = datetime.utcnow()

    nfd_str = (form.get("next_followup_date") or "").strip()
    if not nfd_str:
        raise HTTPException(status_code=400, detail="next_followup_date is required")
    try:
        lead.next_followup_date = datetime.fromisoformat(nfd_str) - _IST_OFFSET
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid next_followup_date format.")

    snapshot = LeadUpdate(
        tenant_id=tenant.id,
        lead_id=lead_id,
        sales_exec_id=user_id,
        sales_exec_name=user_name,
        company_name=lead.company_name,
        client_name=lead.client_name,
        client_phone=lead.client_phone,
        site_status=lead.site_status,
        stage=lead.stage,
        material=lead.material,
        grade=lead.grade,
        quantity=lead.quantity,
        remarks=lead.remarks,
    )
    db.add(snapshot)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")

    from bot.scheduler import reschedule_on_update
    reschedule_on_update(lead.id, user_id, lead.stage, telegram_app.bot, request.app.state.bot_loop)

    print(f"✏️ Lead #{lead_id} updated by {user_name} ({user_id}) [tenant={tenant.slug}]")
    return {"status": "ok", "lead_id": lead.id}


# ── Stats, Goals, History ─────────────────────────────────────────────────────────────

@router.get("/api/stats")
async def api_stats(
    user_id: int,
    tenant: Tenant = Depends(require_miniapp_auth),
    db: Session = Depends(get_db),
):
    q = db.query(Lead).filter(Lead.tenant_id == tenant.id, Lead.sales_exec_id == user_id)
    total       = q.count()
    won         = q.filter(Lead.site_status == "Won").count()
    lost        = q.filter(Lead.site_status == "Lost").count()
    recent      = q.order_by(Lead.created_at.desc()).limit(10).all()
    return {
        "total": total, "won": won, "lost": lost,
        "in_progress": max(total - won - lost, 0),
        "recent": [{
            "id": l.id, "company_name": l.company_name, "client_name": l.client_name,
            "site_status": l.site_status, "stage": l.stage,
            "material": l.material, "quantity": l.quantity,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        } for l in recent],
    }


@router.get("/api/goals")
async def api_goals(
    user_id: int,
    tenant: Tenant = Depends(require_miniapp_auth),
    db: Session = Depends(get_db),
):
    from models.tenant_config import get_config

    now_utc = datetime.now(timezone.utc)
    start   = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q       = db.query(Lead).filter(Lead.tenant_id == tenant.id, Lead.sales_exec_id == user_id)
    qm      = q.filter(Lead.created_at >= start)

    this_month = qm.count()
    won        = qm.filter(Lead.site_status == "Won").count()
    total_qty  = 0.0
    for l in qm.filter(Lead.quantity.isnot(None)).all():
        try:    total_qty += float(l.quantity)
        except: pass

    target = db.query(ExecTarget).filter(
        ExecTarget.tenant_id == tenant.id,
        ExecTarget.sales_exec_id == user_id,
    ).first()

    # Fall back to tenant-level defaults from config
    default_leads  = get_config(db, tenant.id, "default_monthly_leads",  30)
    default_conv   = get_config(db, tenant.id, "default_conversion_pct", 40.0)
    default_volume = get_config(db, tenant.id, "default_volume_m3",      500.0)

    return {
        "this_month": this_month, "won": won, "total_quantity": round(total_qty, 2),
        "goals": {
            "monthly_target":    target.monthly_leads  if target else default_leads,
            "conversion_target": target.conversion_pct if target else default_conv,
            "volume_target":     target.volume_m3      if target else default_volume,
        },
    }


@router.get("/api/history")
async def api_history(
    user_id: int,
    tenant: Tenant = Depends(require_miniapp_auth),
    db: Session = Depends(get_db),
):
    leads = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant.id, Lead.sales_exec_id == user_id)
        .order_by(Lead.created_at.desc())
        .limit(50).all()
    )
    lead_ids = [l.id for l in leads]
    updates  = (
        db.query(LeadUpdate)
        .filter(LeadUpdate.lead_id.in_(lead_ids))
        .order_by(LeadUpdate.updated_at.asc()).all()
    ) if lead_ids else []

    upd_by_lead: dict = {}
    for u in updates:
        upd_by_lead.setdefault(u.lead_id, []).append({
            "id": u.id, "site_status": u.site_status, "stage": u.stage,
            "material": u.material, "quantity": u.quantity, "remarks": u.remarks,
            "updated_at": u.updated_at.isoformat() if u.updated_at else None,
        })

    return {"leads": [{
        "id": l.id, "company_name": l.company_name, "client_name": l.client_name,
        "client_phone": l.client_phone, "site_status": l.site_status,
        "stage": l.stage, "material": l.material, "grade": l.grade,
        "quantity": l.quantity, "remarks": l.remarks, "location": l.location,
        "created_at":         l.created_at.isoformat()         if l.created_at else None,
        "last_followup_at":   l.last_followup_at.isoformat()   if l.last_followup_at else None,
        "next_followup_date": l.next_followup_date.isoformat() if l.next_followup_date else None,
        "is_overdue":         _is_overdue(l),
        "updates":            upd_by_lead.get(l.id, []),
    } for l in leads]}
