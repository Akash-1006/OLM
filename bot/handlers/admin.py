# bot/handlers/admin.py
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import func
from models.lead import Lead
from models.followup import FollowUp
from db import SessionLocal
from datetime import datetime, timedelta


# ── helpers ────────────────────────────────────────────────────────────────────

def fmt_leads(leads):
    """Format a list of Lead rows into a readable string."""
    if not leads:
        return "No leads found."
    lines = []
    for l in leads:
        lines.append(
            f"#{l.id} | {l.location} | {l.client_name} | "
            f"{l.site_status} | {l.created_at.strftime('%d %b %Y')}"
        )
    return "\n".join(lines)


# ── /leads ─────────────────────────────────────────────────────────────────────

async def cmd_leads(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """List all leads added in the last 7 days."""
    session = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(days=7)
        leads = session.query(Lead).filter(Lead.created_at >= since).all()
        text = f"📋 Leads (last 7 days) — {len(leads)} total\n\n" + fmt_leads(leads)
        await update.message.reply_text(text)
    finally:
        session.close()


# ── /report ────────────────────────────────────────────────────────────────────

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Summary: total leads, conversion %, top loss reasons."""
    session = SessionLocal()
    try:
        total_leads = session.query(Lead).count()

        converted   = session.query(FollowUp).filter(FollowUp.status == "converted").count()
        lost        = session.query(FollowUp).filter(FollowUp.status == "lost").count()
        in_progress = session.query(FollowUp).filter(FollowUp.status == "progress").count()

        reasons = (
            session.query(FollowUp.detail, func.count(FollowUp.detail).label("cnt"))
            .filter(FollowUp.status == "lost")
            .group_by(FollowUp.detail)
            .order_by(func.count(FollowUp.detail).desc())
            .all()
        )

        pct = round((converted / total_leads * 100), 1) if total_leads else 0

        reason_lines = "\n".join(
            f"  • {r.detail}: {r.cnt}" for r in reasons
        ) or "  None yet"

        text = (
            f"📊 Sales Report\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Total Leads    : {total_leads}\n"
            f"✅ Converted   : {converted} ({pct}%)\n"
            f"❌ Not Converted: {lost}\n"
            f"⏳ In Progress  : {in_progress}\n\n"
            f"Loss Reasons:\n{reason_lines}"
        )
        await update.message.reply_text(text)
    finally:
        session.close()


# ── /pending ───────────────────────────────────────────────────────────────────

async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show leads older than 3 days with no follow-up response yet."""
    session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=3)
        followed_up_ids = [
            fu.lead_id for fu in session.query(FollowUp.lead_id).distinct()
        ]
        pending = session.query(Lead).filter(
            Lead.created_at <= cutoff,
            ~Lead.id.in_(followed_up_ids) if followed_up_ids else True
        ).all()
        text = f"⚠️ Pending Leads (no follow-up) — {len(pending)}\n\n" + fmt_leads(pending)
        await update.message.reply_text(text)
    finally:
        session.close()


# ── /lead <id> ─────────────────────────────────────────────────────────────────

async def cmd_lead_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show full detail of one lead + all its follow-up history."""
    session = SessionLocal()
    try:
        if not ctx.args:
            await update.message.reply_text("Usage: /lead <id>  e.g. /lead 12")
            return

        try:
            lead_id = int(ctx.args[0])
        except ValueError:
            await update.message.reply_text("ID must be a number. e.g. /lead 12")
            return

        lead = session.get(Lead, lead_id)
        if not lead:
            await update.message.reply_text(f"No lead found with ID {lead_id}")
            return

        followups = (
            session.query(FollowUp)
            .filter(FollowUp.lead_id == lead_id)
            .order_by(FollowUp.recorded_at)
            .all()
        )

        fu_lines = "\n".join(
            f"  [{fu.recorded_at.strftime('%d %b')}] {fu.status} — {fu.detail}"
            for fu in followups
        ) or "  No follow-ups recorded yet"

        text = (
            f"📍 Lead #{lead.id}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Location : {lead.location}\n"
            f"Client   : {lead.client_name} | {lead.client_phone}\n"
            f"Status   : {lead.site_status}\n"
            f"Added    : {lead.created_at.strftime('%d %b %Y %H:%M')}\n\n"
            f"Follow-Up History:\n{fu_lines}"
        )
        await update.message.reply_text(text)
    finally:
        session.close()


# ── Register all handlers ──────────────────────────────────────────────────────

def register_admin_handlers(application):
    application.add_handler(CommandHandler("leads",   cmd_leads))
    application.add_handler(CommandHandler("report",  cmd_report))
    application.add_handler(CommandHandler("pending", cmd_pending))
    application.add_handler(CommandHandler("lead",    cmd_lead_detail))