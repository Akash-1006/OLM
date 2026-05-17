# routers/miniapp.py
"""
Mini App routes (Telegram WebApp frontend).

All routes are tenant-aware: every DB query is scoped to tenant.id.
Auth is via require_app_auth (MINIAPP_ACCESS_KEY per tenant).
"""
import json
import os
import io
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session

from db import SessionLocal
from dependencies import get_db, get_current_tenant, require_app_auth
from models.lead import Lead
from models.lead_update import LeadUpdate
from models.exec_target import ExecTarget
from models.tenant import Tenant
from models.tenant_config import get_config
from bot.scheduler import schedule_followups, reschedule_on_update

router = APIRouter(tags=["miniapp"])

_IST = timedelta(hours=5, minutes=30)


def _to_utc(ist_str: str) -> datetime:
    """Parse IST datetime-local string (YYYY-MM-DDTHH:MM) to UTC datetime."""
    dt = datetime.fromisoformat(ist_str)
    return dt - _IST


def _to_ist_str(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return (aware + _IST).strftime("%Y-%m-%dT%H:%M")


# ── Serve Mini App HTML ────────────────────────────────────────────────────────

@router.get("/miniapp", response_class=HTMLResponse)
@router.get("/miniapp/update", response_class=HTMLResponse)
async def serve_miniapp(request: Request, tenant: Tenant = Depends(get_current_tenant)):
    base_url = (
        tenant.miniapp_base_url
        or os.getenv("MINIAPP_BASE_URL", "")
        or os.getenv("WEBHOOK_URL", "")
    ).rstrip("/")

    with open(os.path.join("miniapp", "index.html"), "r") as f:
        html = f.read()

    html = html.replace("https://YOUR_NGROK_OR_DOMAIN", base_url)
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


# ── Tenant config for frontend ───────────────────────────────────────────────────

@router.get("/api/tenant-config")
async def api_tenant_config(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Return the config the mini app needs to render its dropdowns."""
    return {
        "stages":       get_config(db, tenant.id, "stages",       default=[]),
        "materials":    get_config(db, tenant.id, "materials",    default=[]),
        "work_statuses":get_config(db, tenant.id, "work_statuses",default=[]),
        "brand_name":   get_config(db, tenant.id, "brand_name",   default="OLM"),
    }


# ── Auth ───────────────────────────────────────────────────────────────────────────

@router.post("/api/auth")
async def api_auth(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
):
    data = await request.json()
    key  = (data.get("key") or "").strip()
    access_key = tenant.miniapp_access_key or os.getenv("MINIAPP_ACCESS_KEY", "")
    if not access_key or key == access_key:
        return {"status": "ok"}
    raise HTTPException(status_code=401, detail="Invalid access key")


# ── Submit lead ──────────────────────────────────────────────────────────────────

@router.post("/submit_lead")
async def submit_lead(
    request: Request,
    tenant: Tenant = Depends(require_app_auth),
    db: Session = Depends(get_db),
):
    form = await request.form()

    company_name           = (form.get("company_name") or "").strip()
    contact_name           = (form.get("contact_name") or "").strip()
    phone                  = (form.get("phone")        or "").strip()
    work_status            = (form.get("work_status")  or "").strip()
    stage                  = (form.get("stage")        or "").strip()
    material               = (form.get("material")     or "").strip()
    grade                  = (form.get("grade")        or "").strip()
    quantity               = (form.get("quantity")     or "").strip()
    remarks                = (form.get("remarks")      or "").strip()
    next_followup_date_str = (form.get("next_followup_date") or "").strip()

    missing = [k for k, v in {
        "company_name":       company_name,
        "contact_name":       contact_name,
        "phone":              phone,
        "work_status":        work_status,
        "stage":              stage,
        "material":           material,
        "quantity":           quantity,
        "next_followup_date": next_followup_date_str,
    }.items() if not v]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")

    try:
        next_followup_date = _to_utc(next_followup_date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid next_followup_date format")

    try:
        latitude  = float(form.get("latitude"))  if form.get("latitude")  else None
        longitude = float(form.get("longitude")) if form.get("longitude") else None
    except (ValueError, TypeError):
        latitude = longitude = None

    if not latitude or not longitude:
        raise HTTPException(status_code=400, detail="Location is required")

    try:
        tg_user = json.loads(form.get("tg_user") or "{}")
    except Exception:
        tg_user = {}

    chat_id   = tg_user.get("id")
    user_name = (
        tg_user.get("name")
        or " ".join(filter(None, [tg_user.get("first_name",""), tg_user.get("last_name","")]))
        or tg_user.get("username")
        or "Unknown"
    )

    # Save photos
    UPLOAD_DIR = os.path.join("uploads", "leads")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    photo_paths = []
    for key in form:
        if key.startswith("photo_"):
            file = form[key]
            if hasattr(file, "filename") and file.filename:
                content = await file.read()
                filename = f"{chat_id or 'unknown'}_{key}_{file.filename}"
                save_path = os.path.join(UPLOAD_DIR, filename)
                with open(save_path, "wb") as fp:
                    fp.write(content)
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

        if chat_id:
            schedule_followups(
                lead_id=lead.id,
                chat_id=chat_id,
                bot=request.app.state.bot,
                loop=request.app.state.loop,
                stage=stage,
            )

        print(f"✅ Lead #{lead.id} saved — {company_name} | tenant={tenant.id}")
        return {"status": "ok", "lead_id": lead.id}

    except Exception as e:
        db.rollback()
        print(f"❌ DB error: {e}")
        raise HTTPException(status_code=500, detail="Database error")


# ── Get lead detail (for update form) ─────────────────────────────────────────────

@router.get("/api/lead/{lead_id}")
async def api_lead_detail(
    lead_id: int,
    user_id: int = Query(...),
    tenant: Tenant = Depends(require_app_auth),
    db: Session = Depends(get_db),
):
    lead = (
        db.query(Lead)
        .filter(
            Lead.id == lead_id,
            Lead.tenant_id == tenant.id,
            Lead.sales_exec_id == user_id,
        )
        .first()
    )
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


# ── Update lead ──────────────────────────────────────────────────────────────────

@router.post("/api/lead/{lead_id}/update")
async def api_update_lead(
    lead_id: int,
    request: Request,
    tenant: Tenant = Depends(require_app_auth),
    db: Session = Depends(get_db),
):
    form = await request.form()
    try:
        tg_user   = json.loads(form.get("tg_user") or "{}")
        user_id   = tg_user.get("id")
        user_name = (
            tg_user.get("name")
            or " ".join(filter(None, [tg_user.get("first_name",""), tg_user.get("last_name","")]))
            or tg_user.get("username")
            or "Unknown"
        )
    except Exception:
        user_id = user_name = None

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    lead = (
        db.query(Lead)
        .filter(
            Lead.id == lead_id,
            Lead.tenant_id == tenant.id,
            Lead.sales_exec_id == user_id,
        )
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Apply field updates
    for field, col in [
        ("company_name", "company_name"), ("contact_name", "client_name"),
        ("phone", "client_phone"),        ("work_status",  "site_status"),
        ("stage", "stage"),               ("material",     "material"),
        ("grade", "grade"),               ("quantity",     "quantity"),
        ("remarks", "remarks"),
    ]:
        val = form.get(field)
        if val:
            setattr(lead, col, val.strip())

    lead.last_user_update_at = datetime.utcnow()

    nfd_str = (form.get("next_followup_date") or "").strip()
    if not nfd_str:
        raise HTTPException(status_code=400, detail="next_followup_date is required")
    try:
        lead.next_followup_date = _to_utc(nfd_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid next_followup_date format")

    snapshot = LeadUpdate(
        lead_id=lead_id,
        tenant_id=tenant.id,
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
        reschedule_on_update(
            lead.id, user_id, lead.stage,
            request.app.state.bot,
            request.app.state.loop,
        )
        return {"status": "ok", "lead_id": lead.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


# ── Stats ───────────────────────────────────────────────────────────────────────────

@router.get("/api/stats")
async def api_stats(
    user_id: int = Query(...),
    tenant: Tenant = Depends(require_app_auth),
    db: Session = Depends(get_db),
):
    q = db.query(Lead).filter(Lead.sales_exec_id == user_id, Lead.tenant_id == tenant.id)
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
        } for l in recent]
    }


# ── Goals ───────────────────────────────────────────────────────────────────────────

@router.get("/api/goals")
async def api_goals(
    user_id: int = Query(...),
    tenant: Tenant = Depends(require_app_auth),
    db: Session = Depends(get_db),
):
    now        = datetime.now(timezone.utc)
    start      = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q          = db.query(Lead).filter(Lead.sales_exec_id == user_id, Lead.tenant_id == tenant.id)
    qm         = q.filter(Lead.created_at >= start)
    this_month = qm.count()
    won        = qm.filter(Lead.site_status == "Won").count()

    total_qty  = sum(
        (lambda v: float(v) if v else 0.0)(l.quantity)
        for l in qm.filter(Lead.quantity.isnot(None)).all()
        if l.quantity
    )

    target = db.query(ExecTarget).filter(
        ExecTarget.sales_exec_id == user_id, ExecTarget.tenant_id == tenant.id
    ).first()

    return {
        "this_month":     this_month,
        "won":            won,
        "total_quantity": round(total_qty, 2),
        "goals": {
            "monthly_target":    target.monthly_leads  if target else get_config(db, tenant.id, "default_monthly_leads", 30),
            "conversion_target": target.conversion_pct if target else get_config(db, tenant.id, "default_conversion_pct", 40.0),
            "volume_target":     target.volume_m3      if target else get_config(db, tenant.id, "default_volume_m3", 500.0),
        },
    }


# ── History ─────────────────────────────────────────────────────────────────────────

def _is_overdue(l) -> bool:
    IST = timezone(timedelta(hours=5, minutes=30))
    if l.site_status in ("Won", "Lost") or not l.last_followup_at:
        return False
    if l.last_user_update_at and l.last_user_update_at >= l.last_followup_at:
        return False
    lfa_ist  = l.last_followup_at.replace(tzinfo=timezone.utc).astimezone(IST)
    deadline = lfa_ist.replace(hour=18, minute=30, second=0, microsecond=0)
    return datetime.now(timezone.utc).astimezone(IST) > deadline


@router.get("/api/history")
async def api_history(
    user_id: int = Query(...),
    tenant: Tenant = Depends(require_app_auth),
    db: Session = Depends(get_db),
):
    leads = (
        db.query(Lead)
        .filter(Lead.sales_exec_id == user_id, Lead.tenant_id == tenant.id)
        .order_by(Lead.created_at.desc())
        .limit(50).all()
    )
    lead_ids = [l.id for l in leads]
    updates  = (
        db.query(LeadUpdate)
        .filter(LeadUpdate.lead_id.in_(lead_ids))
        .order_by(LeadUpdate.updated_at.asc())
        .all()
    ) if lead_ids else []

    updates_by_lead = {}
    for u in updates:
        updates_by_lead.setdefault(u.lead_id, []).append({
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
        "updates":            updates_by_lead.get(l.id, []),
    } for l in leads]}


# ── Generate Quote ─────────────────────────────────────────────────────────────

@router.post("/generate_quote")
async def generate_quote(
    request: Request,
    tenant: Tenant = Depends(require_app_auth),
):
    data     = await request.json()
    company  = (data.get("company_name") or "").strip()
    quantity = (data.get("quantity")     or "").strip()
    grade    = (data.get("grade")        or "").strip()
    rate     = (data.get("rate")         or "").strip()
    location = (data.get("location")     or "").strip()
    user_id  = data.get("user_id")

    try:
        tg_user = json.loads(data["tg_user"]) if isinstance(data.get("tg_user"), str) else data.get("tg_user", {})
    except Exception:
        tg_user = {}

    chat_id   = tg_user.get("id") or user_id
    exec_name = (
        " ".join(filter(None, [tg_user.get("first_name",""), tg_user.get("last_name","")])).strip()
        or tg_user.get("username")
        or "Executive"
    )

    if not all([company, quantity, grade, rate, location, chat_id]):
        raise HTTPException(status_code=400, detail="Missing required fields")

    TEMPLATE_PATH = os.path.join(os.getenv("QUOTE_TEMPLATE_DIR", "static"), "quote_template.pdf")
    if not os.path.exists(TEMPLATE_PATH):
        raise HTTPException(status_code=500, detail=f"Quote template not found at '{TEMPLATE_PATH}'")

    from bot.quote_generator import build_quote_pdf
    buf = io.BytesIO()
    build_quote_pdf(
        out_buf=buf, template_path=TEMPLATE_PATH,
        company=company, location=location,
        quantity=quantity, grade=grade, rate=rate, exec_name=exec_name,
    )
    buf.seek(0)

    now_ist  = datetime.now(timezone(_IST))
    date_str = now_ist.strftime("%d %b %Y")
    filename = f"OLM_Quote_{company.replace(' ','_')}_{date_str.replace(' ','')}.pdf"

    try:
        qty_f  = float(quantity)
    except Exception:
        qty_f  = 0.0
    try:
        rate_f = float(rate)
    except Exception:
        rate_f = 0.0

    await request.app.state.bot.send_document(
        chat_id=int(chat_id),
        document=buf,
        filename=filename,
        caption=(
            f"📄 *Quote — {company}*\n"
            f"📍 {location}  |  🏗 {grade}  |  📦 {qty_f:.0f} cum\n"
            f"💰 Rate: ₹{rate_f:,.0f}/cum (incl. GST)"
        ),
        parse_mode="Markdown",
    )
    return {"status": "ok", "filename": filename}
