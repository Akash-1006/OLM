# bot/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta, timezone
import asyncio
import os

scheduler = BackgroundScheduler(timezone="UTC")
scheduler.start()

def _utcnow() -> datetime:
    """Return current time as timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

# ── TEST MODE ─────────────────────────────────────────────────────────────────
# Set TEST_MODE=1 in your .env to compress days → minutes for quick testing.
#
#   Production:  Pile=1d, Footing/Slab=3d, Flooring=4d, Column=7d
#   Test mode:   Pile=1m, Footing/Slab=3m, Flooring=4m, Column=7m
#
# To test: set TEST_MODE=1, restart, submit a lead, watch reminders arrive.
# To revert: remove TEST_MODE (or set to 0), restart.

_TEST_MODE = os.getenv("TEST_MODE", "0").strip() == "1"

if _TEST_MODE:
    print("⚠️  SCHEDULER TEST MODE ON — cadence is in MINUTES not days")

# ── Reminder cadence per stage ────────────────────────────────────────────────
# interval_days: how often to repeat   |   max_reminders: stop after N sends
STAGE_CADENCE = {
    "Pile":     {"interval_days": 1,  "max_reminders": 30},  # daily        → 1 min in test
    "Footing":  {"interval_days": 3,  "max_reminders": 10},  # every 3 days → 3 min in test
    "Slab":     {"interval_days": 3,  "max_reminders": 10},  # every 3 days → 3 min in test
    "Flooring": {"interval_days": 4,  "max_reminders": 8},   # every 4 days → 4 min in test
    "Column":   {"interval_days": 7,  "max_reminders": 6},   # every 7 days → 7 min in test
}
DEFAULT_CADENCE = {"interval_days": 3, "max_reminders": 10}

# In test mode use smaller limits so chat doesn't flood
_TEST_MAX = 5


def _interval(days: int) -> timedelta:
    """Return timedelta in days (prod) or minutes (test mode)."""
    if _TEST_MODE:
        return timedelta(minutes=days)
    return timedelta(days=days)


def _fmt_delta(td: timedelta) -> str:
    """Format a timedelta as a human-readable string."""
    total = int(abs(td.total_seconds()))
    if total < 60:
        return f"{total}s"
    if total < 3600:
        m, s = divmod(total, 60)
        return f"{m}m {s}s"
    if total < 86400:
        h, rem = divmod(total, 3600)
        m = rem // 60
        return f"{h}h {m}m"
    d, rem = divmod(total, 86400)
    h = rem // 3600
    return f"{d}d {h}h"


def _cancel_pending_jobs(lead_id: int):
    """Remove the follow-up job for a lead from the scheduler."""
    job_id = f"followup_{lead_id}"
    job = scheduler.get_job(job_id)
    if job:
        try:
            job.remove()
            print(f"🗑  Cancelled pending job for lead #{lead_id}")
        except Exception:
            pass


def _schedule_single(lead_id, chat_id, bot, loop, stage, run_time, count, retry_count=0):
    """Schedule one reminder for a lead. Uses a stable job ID to prevent duplicates."""
    job_id = f"followup_{lead_id}"
    scheduler.add_job(
        send_followup_reminder,
        trigger=DateTrigger(run_date=run_time),
        args=[lead_id, chat_id, bot, loop, stage, count, retry_count],
        id=job_id,
        replace_existing=True,
    )


def schedule_followups(lead_id: int, chat_id: int, bot, loop, stage: str = None, count: int = 1):
    """
    Ensure a follow-up reminder is scheduled for a lead based on its stage and last activity.
    """
    from db import SessionLocal
    from models.lead import Lead
    from models.lead_update import LeadUpdate
    from sqlalchemy import func

    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead or lead.site_status in ("Won", "Lost"):
            _cancel_pending_jobs(lead_id)
            return

        # Helper to ensure DB times are UTC-aware
        def _to_aware(dt):
            if dt and dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        # Check latest activity (creation or update)
        latest_upd = session.query(func.max(LeadUpdate.updated_at)).filter(LeadUpdate.lead_id == lead_id).scalar()
        
        la_upd = _to_aware(latest_upd)
        la_cre = _to_aware(lead.created_at)
        
        if la_upd and la_cre:
            last_activity = la_upd if la_upd > la_cre else la_cre
        else:
            last_activity = la_upd or la_cre or _utcnow()
        
        # Also consider when the last reminder was sent
        if lead.last_followup_at:
            lfa = _to_aware(lead.last_followup_at)
            if not last_activity or lfa > last_activity:
                last_activity = lfa

        # Ensure final last_activity is aware
        last_activity = _to_aware(last_activity)

        current_stage = lead.stage or stage or ""
        cadence  = STAGE_CADENCE.get(current_stage, DEFAULT_CADENCE)
        interval = cadence["interval_days"]
        
        # Calculate next run: last_activity + interval
        next_run = last_activity + _interval(interval)
        
        # If next_run is in the past, schedule for very soon
        now = _utcnow()
        if next_run < now:
            next_run = now + timedelta(seconds=10)

        _schedule_single(lead_id, chat_id, bot, loop, current_stage, run_time=next_run, count=count)

        unit = "min" if _TEST_MODE else "day"
        print(f"📅 Scheduled follow-up for lead #{lead_id} at {next_run} "
              f"(stage: {current_stage}, interval: {interval} {unit})")
    finally:
        session.close()


def sync_scheduler_with_db(bot, loop):
    """
    Scan DB for all active leads and ensure they have a follow-up job scheduled.
    Called at startup and periodically to maintain robustness.
    """
    from db import SessionLocal
    from models.lead import Lead
    
    print("🔄 Syncing scheduler with database...")
    session = SessionLocal()
    try:
        # Leads NOT Won or Lost
        active_leads = session.query(Lead).filter(~Lead.site_status.in_(["Won", "Lost"])).all()
        for lead in active_leads:
            # We don't know the exact count, so we'll start at 1 if no job exists.
            # If a job exists, APScheduler will keep it unless we overwrite.
            job_id = f"followup_{lead.id}"
            if not scheduler.get_job(job_id):
                schedule_followups(lead.id, lead.sales_exec_id, bot, loop, lead.stage, count=1)
        
        # Also cleanup jobs for leads that ARE now Won/Lost or deleted
        all_jobs = scheduler.get_jobs()
        for job in all_jobs:
            if job.id.startswith("followup_"):
                try:
                    lead_id = int(job.id.replace("followup_", ""))
                    lead = session.query(Lead).filter(Lead.id == lead_id).first()
                    if not lead or lead.site_status in ("Won", "Lost"):
                        job.remove()
                        print(f"🗑  Removed stale job for lead #{lead_id}")
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        print(f"❌ Scheduler sync failed: {e}")
    finally:
        session.close()
    print_scheduler_status()
    print("✅ Scheduler sync complete")


def reschedule_on_update(lead_id: int, chat_id: int, new_stage: str, bot, loop):
    """
    Explicitly reschedule follow-up after an update.
    """
    schedule_followups(lead_id, chat_id, bot, loop, new_stage, count=1)


def print_scheduler_status():
    """
    Print all scheduled follow-up jobs and flag any upcoming/overdue ones.
    Called at startup and via /admin/api/scheduler-status.
    """
    from db import SessionLocal
    from models.lead import Lead

    IST = timezone(timedelta(hours=5, minutes=30))
    now = _utcnow()

    jobs = [j for j in scheduler.get_jobs() if j.id.startswith("followup_")]

    if not jobs:
        print("📭  No follow-up jobs currently scheduled")
        return

    print(f"\n{'─'*60}")
    print(f"📅  SCHEDULED FOLLOW-UPS  ({len(jobs)} job(s))  |  "
          f"Now: {now.astimezone(IST).strftime('%d %b %H:%M IST')}")
    print(f"{'─'*60}")

    # Group by lead_id
    by_lead: dict = {}
    for job in jobs:
        # New format: followup_{lead_id} (count is in args[5])
        # Old format: followup_{lead_id}_{count}
        parts = job.id.split("_")
        if len(parts) == 2:
            lead_id = int(parts[1])
            count = job.args[5] if (len(job.args) > 5) else 1
            by_lead.setdefault(lead_id, []).append((count, job))
        elif len(parts) >= 3:
            lead_id = int(parts[1])
            count   = int(parts[2])
            by_lead.setdefault(lead_id, []).append((count, job))

    session = SessionLocal()
    try:
        for lead_id, job_list in sorted(by_lead.items()):
            lead   = session.query(Lead).filter(Lead.id == lead_id).first()
            name   = (lead.company_name or lead.client_name or f"Lead #{lead_id}") if lead else f"Lead #{lead_id}"
            stage  = (lead.stage or "?") if lead else "?"
            status = (lead.site_status or "?") if lead else "?"

            print(f"\n  Lead #{lead_id}  {name}  [{stage}]  status={status}")

            for count, job in sorted(job_list):
                next_run = job.next_run_time
                if next_run is None:
                    label = "⏸  paused"
                else:
                    delta      = next_run - now
                    ist_str    = next_run.astimezone(IST).strftime("%d %b %H:%M IST")
                    total_secs = delta.total_seconds()
                    if total_secs < 0:
                        label = f"⚠️  MISSED by {_fmt_delta(-delta)} — fires at {ist_str}"
                    elif total_secs < 3600:
                        label = f"⏰  in {_fmt_delta(delta)} — {ist_str}"
                    else:
                        label = f"🕐  {ist_str} (in {_fmt_delta(delta)})"

                print(f"    Reminder #{count:2d}  {label}")
    finally:
        session.close()

    print(f"{'─'*60}\n")


def send_followup_reminder(lead_id: int, chat_id: int, bot, loop,
                            stage: str = None, count: int = 1, retry_count: int = 0):
    """
    Fetch lead from DB, send reminder, then schedule the next one
    if max_reminders has not been reached and the lead isn't Won/Lost.
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    from db import SessionLocal
    from models.lead import Lead

    MINIAPP_BASE = (
        os.getenv("MINIAPP_BASE_URL") or
        os.getenv("WEBHOOK_URL") or ""
    ).rstrip("/")

    if not MINIAPP_BASE:
        print(f"❌ MINIAPP_BASE_URL and WEBHOOK_URL are both empty — cannot build update URL")
        return

    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            print(f"⚠️ Lead #{lead_id} not found — cancelling reminders")
            _cancel_pending_jobs(lead_id)
            return

        # Stop reminders if lead is closed or Won/Lost (as per user request)
        if lead.site_status in ("Won", "Lost") or (lead.stage and lead.stage.lower() in ("won", "lost")):
            print(f"🛑 Lead #{lead_id} is {lead.site_status or lead.stage} — stopping reminders")
            _cancel_pending_jobs(lead_id)
            return

        # Use current stage from DB
        from sqlalchemy import func
        from models.lead_update import LeadUpdate

        def _to_aware(dt):
            if dt and dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        latest_upd = session.query(func.max(LeadUpdate.updated_at)).filter(LeadUpdate.lead_id == lead_id).scalar()
        
        la_upd = _to_aware(latest_upd)
        la_cre = _to_aware(lead.created_at)

        if la_upd and la_cre:
            last_activity = la_upd if la_upd > la_cre else la_cre
        else:
            last_activity = la_upd or la_cre or _utcnow()

        current_stage = lead.stage or stage or ""
        cadence       = STAGE_CADENCE.get(current_stage, DEFAULT_CADENCE)
        interval      = cadence["interval_days"]
        
        # ── DB-Driven Timing Check ───────────────────────────────────────────
        now = _utcnow()
        interval_td = _interval(interval)
        
        # Check against both last human activity and last successful reminder send
        last_any_event = last_activity
        if lead.last_followup_at:
            lfa = _to_aware(lead.last_followup_at)
            if lfa > last_any_event:
                last_any_event = lfa
        
        # Ensure aware comparison
        last_any_event = _to_aware(last_any_event)

        # Safety margin is the full interval for new reminders, or 5 mins for retries 
        # (to catch cases where a 'timed out' job actually went through).
        safety_margin = interval_td if not retry_count else timedelta(minutes=5)

        if last_any_event and now < last_any_event + safety_margin - timedelta(seconds=15):
            # Already sent recently or too early.
            new_run = last_any_event + interval_td
            if not retry_count:
                print(f"⏳ Lead #{lead_id} had recent activity/reminder ({last_any_event}). Rescheduling to {new_run}")
                _schedule_single(lead_id, chat_id, bot, loop, current_stage, new_run, count)
            else:
                print(f"🛑 Retry for lead #{lead_id} (reminder #{count}) blocked — record shows it was already sent at {last_any_event}")
            return

        # ── Stage change detection ─────────────────────────────────────────────
        stage_changed = (stage or "") != current_stage
        if stage_changed:
            print(f"🔄 Lead #{lead_id} stage changed: {stage or '—'} → {current_stage} — resetting sequence")
            count = 1   # restart the reminder sequence

        max_reminders = _TEST_MAX if _TEST_MODE else cadence["max_reminders"]

        # Build location line
        if lead.latitude and lead.longitude:
            location_line = f"\n🗺 https://www.google.com/maps?q={lead.latitude},{lead.longitude}"
        else:
            location_line = f"\n📍 {lead.location or 'Location not set'}"

        # Material with grade
        material_str = lead.material or "—"
        if lead.grade:
            material_str += f" ({lead.grade})"

        # Cadence label for message footer
        cadence_label = {
            1: "Daily reminder",
            3: "3-day follow-up",
            4: "4-day follow-up",
            7: "Weekly follow-up",
        }.get(interval, f"Every {interval}-day follow-up")

        stage_changed_note = (
            f"\n_⚠️ Stage updated: now tracking as {current_stage}_"
            if stage_changed else ""
        )

        text = (
            f"📋 *Lead Follow-up #{count}:* {lead.company_name or '—'}\n"
            f"👤 Contact: {lead.client_name or '—'}\n"
            f"📞 Phone: {lead.client_phone or '—'}\n"
            f"🏗 Stage: {current_stage or '—'}\n"
            f"📦 Material: {material_str}\n"
            f"📊 Quantity: {lead.quantity or '—'}\n"
            f"✅ Status: {lead.site_status or '—'}\n"
            f"💬 Remarks: {lead.remarks or '—'}\n"
            f"_{cadence_label} for {current_stage or 'site'} stage._"
            f"{stage_changed_note}"
            f"{location_line}"
        )

        update_url = f"{MINIAPP_BASE}/miniapp/update?lead_id={lead_id}"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "📝 Update Submission",
                web_app=WebAppInfo(url=update_url)
            )
        ]])

    finally:
        session.close()

    # ── Send the message ──────────────────────────────────────────────────────
    async def _send():
        # Coroutine performs both the send AND the DB update
        # This way, if the caller times out, the DB still reflects the success
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=False,
        )
        
        # Update DB on success — even if caller times out, this coroutine keeps running
        s = SessionLocal()
        try:
            db_l = s.query(Lead).filter(Lead.id == lead_id).first()
            if db_l:
                db_l.last_followup_at = _utcnow()
                s.commit()
                print(f"💾 Updated last_followup_at for lead #{lead_id}")
        except Exception as e:
            print(f"❌ Async DB update failed for lead #{lead_id}: {e}")
        finally:
            s.close()

    future = asyncio.run_coroutine_threadsafe(_send(), loop)
    try:
        # Increased timeout to 50s to handle extreme network latency
        future.result(timeout=50)
        
        unit = "min" if _TEST_MODE else "d"
        print(f"✅ Reminder #{count} sent to {chat_id} for lead #{lead_id} "
              f"(stage: {current_stage}, every {interval}{unit})")
    except Exception as e:
        print(f"❌ Failed to send reminder to {chat_id} for lead #{lead_id}: {e}")
        
        # FAIL PROOF LOGIC: If sending fails, try again after 2 mins (up to 5 times)
        if retry_count < 5:
            retry_time = _utcnow() + timedelta(minutes=2)
            print(f"🔄 Retrying lead #{lead_id} (reminder #{count}, attempt {retry_count+1}/5) in 2 mins...")
            _schedule_single(lead_id, chat_id, bot, loop, current_stage, retry_time, count, retry_count+1)
            return
        else:
            print(f"🚨 Max retries ({retry_count}) reached for lead #{lead_id} reminder #{count}. Moving to next interval.")

    # ── Schedule next reminder if limit not reached ───────────────────────────
    next_count = count + 1
    if next_count <= max_reminders:
        next_run = _utcnow() + _interval(interval)
        _schedule_single(lead_id, chat_id, bot, loop, current_stage,
                         run_time=next_run, count=next_count)
        unit = "min" if _TEST_MODE else "day"
        print(f"📅 Next reminder #{next_count} for lead #{lead_id} "
              f"in {interval} {unit}{'s' if interval>1 else ''}")
    else:
        print(f"🏁 Reached max reminders ({max_reminders}) for lead #{lead_id}")