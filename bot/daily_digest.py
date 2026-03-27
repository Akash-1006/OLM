# bot/daily_digest.py
"""
Daily digest messages sent at a configurable time (default 8:00 PM IST).

Each sales exec receives a summary of the leads they submitted today.
The organisation owner receives a full team summary of all leads today.

Required env vars:
    DIGEST_OWNER_CHAT_ID   — Telegram chat_id of the org owner
                             Get it by messaging @userinfobot on Telegram

Optional env vars:
    DIGEST_TIME_IST        — "HH:MM" in IST, default "20:00"  (8 PM IST)

KEY FIX: bot and loop are looked up lazily at fire time from app-level globals,
not captured at registration time. This avoids stale references when the
scheduler starts before the bot is fully initialized.
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# ── App-level references set by app.py after bot is ready ─────────────────────
# These are populated by register_daily_digest() and used lazily at fire time.
_bot_ref  = None
_loop_ref = None


def _ist_now():
    return datetime.now(IST)


def _today_utc_range():
    """Return (start_utc, end_utc) covering today 00:00–23:59 IST."""
    now_ist   = _ist_now()
    start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    end_ist   = start_ist + timedelta(days=1)
    return (
        start_ist.astimezone(timezone.utc),
        end_ist.astimezone(timezone.utc),
    )


# ── Message builders ───────────────────────────────────────────────────────────

def _lead_line(l) -> str:
    material = _escape(l.material or "—")
    if l.grade:
        material += f" \\({_escape(l.grade)}\\)"
    return (
        f"  • *\\#{l.id}* {_escape(l.company_name or l.client_name or '—')} \\| "
        f"{_escape(l.stage or '—')} \\| {material} \\| {_escape(l.quantity or '—')} \\| {_escape(l.site_status or '—')}"
        + (f"\n    💬 _{_escape(l.remarks)}_" if l.remarks else "")
    )


def _escape(text: str) -> str:
    """Escape special characters for MarkdownV2."""
    special = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in special else c for c in str(text))


def _build_exec_digest(exec_name: str, leads: list) -> str:
    date_str  = _ist_now().strftime("%d %b %Y")
    safe_name = _escape(exec_name)

    if not leads:
        return (
            f"📋 *Daily Lead Summary — {date_str}*\n"
            f"Hi {safe_name}\\! No leads submitted by you today\\.\n"
            f"Keep pushing — every visit counts\\! 💪"
        )

    won   = sum(1 for l in leads if l.site_status == "Won")
    lost  = sum(1 for l in leads if l.site_status == "Lost")
    prog  = len(leads) - won - lost

    lines = [
        f"📋 *Daily Lead Summary — {date_str}*",
        f"Hi *{safe_name}*\\! Here's your activity today:\n",
        f"📊 Total: *{len(leads)}*   ✅ Won: {won}   ❌ Lost: {lost}   ⏳ In Progress: {prog}\n",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for l in leads:
        material = _escape(l.material or "—")
        if l.grade:
            material += f" \\({_escape(l.grade)}\\)"
        lines.append(
            f"\n*\\#{l.id} — {_escape(l.company_name or l.client_name or '—')}*\n"
            f"  👤 {_escape(l.client_name or '—')}   📞 {_escape(l.client_phone or '—')}\n"
            f"  🏗 {_escape(l.stage or '—')}   📦 {material}   📊 {_escape(l.quantity or '—')}\n"
            f"  🔖 {_escape(l.site_status or '—')}"
            + (f"\n  💬 _{_escape(l.remarks)}_" if l.remarks else "")
        )
    lines.append("\nGreat work today\\! 🚀")
    return "\n".join(lines)


def _build_owner_digest(leads: list) -> str:
    date_str = _ist_now().strftime("%d %b %Y")

    if not leads:
        return (
            f"📊 *Mcube Team Summary — {date_str}*\n"
            f"No leads were submitted by the team today\\."
        )

    total = len(leads)
    won   = sum(1 for l in leads if l.site_status == "Won")
    lost  = sum(1 for l in leads if l.site_status == "Lost")
    prog  = total - won - lost

    by_exec: dict[str, list] = {}
    for l in leads:
        name = l.sales_exec_name or f"Exec #{l.sales_exec_id}"
        by_exec.setdefault(name, []).append(l)

    lines = [
        f"📊 *Mcube Team Summary — {date_str}*\n",
        f"📈 Total Leads Today: *{total}*",
        f"✅ Won: {won}   ❌ Lost: {lost}   ⏳ In Progress: {prog}\n",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for exec_name, exec_leads in sorted(by_exec.items()):
        e_won  = sum(1 for l in exec_leads if l.site_status == "Won")
        e_lost = sum(1 for l in exec_leads if l.site_status == "Lost")
        lines.append(
            f"\n👤 *{_escape(exec_name)}*  —  {len(exec_leads)} lead{'s' if len(exec_leads)>1 else ''}"
            f"   \\(✅ {e_won}  ❌ {e_lost}\\)"
        )
        for l in exec_leads:
            lines.append(_lead_line(l))

    lines.append("\n_Mcube M3 · Auto\\-generated daily digest_")
    return "\n".join(lines)


# ── Core send logic ────────────────────────────────────────────────────────────

def _send_message(bot, loop, chat_id: int | str, text: str):
    """Send a Telegram message synchronously from a non-async context."""
    async def _send():
        await bot.send_message(
            chat_id   = int(chat_id),
            text      = text,
            parse_mode= "MarkdownV2",
            disable_web_page_preview=True,
        )
    future = asyncio.run_coroutine_threadsafe(_send(), loop)
    try:
        future.result(timeout=15)
    except Exception as e:
        logger.error("Digest send failed → chat_id=%s: %s", chat_id, e)
        print(f"❌  Digest send failed → chat_id={chat_id}: {e}")


# ── Main digest function ───────────────────────────────────────────────────────

def send_daily_digests(bot=None, loop=None):
    """
    Fetch today's leads and send:
      • one personal digest to EVERY sales exec (even those with 0 leads today)
      • one full-team summary to the owner
    """
    from db import SessionLocal
    from models.lead import Lead
    from sqlalchemy import func

    # Resolve bot and loop — use args if provided, fall back to stored refs
    _bot  = bot  or _bot_ref
    _loop = loop or _loop_ref

    if _bot is None or _loop is None:
        msg = "❌  send_daily_digests: bot or loop not available — was register_daily_digest called?"
        print(msg)
        logger.error(msg)
        return

    owner_chat_id = os.getenv("DIGEST_OWNER_CHAT_ID", "").strip()
    if not owner_chat_id:
        print("⚠️  DIGEST_OWNER_CHAT_ID not set in .env — owner will not receive digest")

    start_utc, end_utc = _today_utc_range()
    date_str = _ist_now().strftime("%d %b %Y %I:%M %p IST")
    print(f"📅  Running daily digest for {date_str}")

    session = SessionLocal()
    try:
        # ── Today's leads ──────────────────────────────────────────────────────
        todays_leads = (
            session.query(Lead)
            .filter(Lead.created_at >= start_utc, Lead.created_at < end_utc)
            .order_by(Lead.sales_exec_id, Lead.created_at)
            .all()
        )
        print(f"📋  Found {len(todays_leads)} lead(s) today")

        # ── All known execs (anyone with at least one lead ever) ───────────────
        all_execs = (
            session.query(
                Lead.sales_exec_id,
                Lead.sales_exec_name,
            )
            .filter(Lead.sales_exec_id.isnot(None))
            .group_by(Lead.sales_exec_id, Lead.sales_exec_name)
            .all()
        )
        print(f"👥  Found {len(all_execs)} exec(s) total")

        # Group today's leads by exec_id
        leads_by_exec: dict = {}
        for l in todays_leads:
            if l.sales_exec_id:
                leads_by_exec.setdefault(l.sales_exec_id, []).append(l)

        # ── Per-exec personal digests (all execs, empty list if no leads today) ─
        sent_execs = 0
        for exec_id, exec_name in all_execs:
            exec_leads = leads_by_exec.get(exec_id, [])   # empty list = no leads today
            name       = exec_name or f"Exec #{exec_id}"
            msg        = _build_exec_digest(name, exec_leads)
            _send_message(_bot, _loop, exec_id, msg)
            sent_execs += 1
            print(f"  ✅ Exec digest → {name} ({exec_id}), {len(exec_leads)} lead(s) today")

        # ── Owner full-team summary ────────────────────────────────────────────
        if owner_chat_id:
            owner_msg = _build_owner_digest(todays_leads)
            _send_message(_bot, _loop, owner_chat_id, owner_msg)
            print(f"  ✅ Owner digest → chat_id={owner_chat_id}, {len(todays_leads)} total lead(s)")

        print(f"✅  Daily digest complete — {sent_execs} exec(s) + {'owner' if owner_chat_id else 'no owner'}")

    except Exception as e:
        print(f"❌  Daily digest error: {e}")
        logger.exception("Daily digest error")
    finally:
        session.close()


# ── Scheduler job wrapper (no args — reads refs set at registration) ───────────

def _scheduled_digest_job():
    """Zero-argument wrapper called by APScheduler cron job."""
    print(f"⏰  APScheduler fired daily digest at {_ist_now().strftime('%H:%M IST')}")
    send_daily_digests()   # uses module-level _bot_ref / _loop_ref


# ── Register with APScheduler ──────────────────────────────────────────────────

def register_daily_digest(scheduler, bot, loop):
    """
    Store bot/loop references and register a daily cron job.

    Must be called AFTER the bot is initialized (i.e. after init_bot() completes).

    Env vars:
        DIGEST_TIME_IST   — e.g. "20:00" (8 PM IST). Default: "20:00"
        DIGEST_OWNER_CHAT_ID — owner's Telegram chat_id
    """
    global _bot_ref, _loop_ref
    _bot_ref  = bot
    _loop_ref = loop

    time_str = os.getenv("DIGEST_TIME_IST", "20:00")
    try:
        h_ist, m_ist = map(int, time_str.strip().split(":"))
    except ValueError:
        print(f"⚠️  Invalid DIGEST_TIME_IST='{time_str}' — defaulting to 20:00 IST")
        h_ist, m_ist = 20, 0

    # IST = UTC+5:30  →  UTC hour = IST - 5h30m
    total_utc = (h_ist * 60 + m_ist - 330) % 1440
    h_utc     = total_utc // 60
    m_utc     = total_utc % 60

    # Remove old job if re-registering
    try:
        scheduler.remove_job("daily_digest")
    except Exception:
        pass

    scheduler.add_job(
        _scheduled_digest_job,
        trigger          = CronTrigger(
                               hour     = h_utc,
                               minute   = m_utc,
                               timezone = "UTC",        # explicit — never ambiguous
                           ),
        id               = "daily_digest",
        replace_existing = True,
        coalesce         = True,    # if multiple misfires stacked up, run once only
        misfire_grace_time = 3600,  # fire even if up to 1h late after restart
    )

    owner = os.getenv("DIGEST_OWNER_CHAT_ID", "").strip()
    print(
        f"📅  Daily digest registered — "
        f"{h_ist:02d}:{m_ist:02d} IST  (UTC {h_utc:02d}:{m_utc:02d})  |  "
        f"Owner: {'set ✅' if owner else 'NOT SET ⚠️  — set DIGEST_OWNER_CHAT_ID in .env'}"
    )