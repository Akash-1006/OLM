# bot/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import asyncio
import os
import random

# 50 threads to handle many concurrent tasks
executors = {'default': ThreadPoolExecutor(50)}
scheduler = BackgroundScheduler(executors=executors, timezone="UTC")
scheduler.start()

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _to_aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def _fmt_delta(td: timedelta) -> str:
    total = int(abs(td.total_seconds()))
    if total < 60: return f"{total}s"
    if total < 3600: return f"{total//60}m {total%60}s"
    if total < 86400: return f"{total//3600}h {(total%3600)//60}m"
    return f"{total//86400}d {(total%86400)//3600}h"

def _cancel_pending_jobs(lead_id: int):
    job_id = f"followup_{lead_id}"
    job = scheduler.get_job(job_id)
    if job:
        try:
            job.remove()
            print(f"🗑  Cancelled pending job for lead #{lead_id}")
        except Exception: pass

def _schedule_single(lead_id, chat_id, bot, loop, stage, run_time, count, retry_count=0):
    job_id = f"followup_{lead_id}"
    scheduler.add_job(
        send_followup_reminder,
        trigger=DateTrigger(run_date=run_time),
        args=[lead_id, chat_id, bot, loop, stage, count, retry_count],
        id=job_id,
        replace_existing=True,
    )

def schedule_followups(lead_id: int, chat_id: int, bot, loop, stage: str = None, count: int = 1, force_delay_sec: int = 0):
    """
    Schedules a reminder. 
    If force_delay_sec > 0, it uses that delay from 'now' (used for staggers).
    Otherwise, it uses the Lead's stored next_followup_date.
    """
    from db import SessionLocal
    from models.lead import Lead

    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead or lead.site_status in ("Won", "Lost") or not lead.next_followup_date:
            _cancel_pending_jobs(lead_id)
            return

        now = _utcnow()
        if force_delay_sec > 0:
            next_run = now + timedelta(seconds=force_delay_sec)
        else:
            next_run = _to_aware(lead.next_followup_date)
            if next_run < now:
                next_run = now + timedelta(seconds=10) # Overdue fire soon

        _schedule_single(lead_id, chat_id, bot, loop, lead.stage or stage or "", next_run, count)

        IST = timezone(timedelta(hours=5, minutes=30))
        print(f"📅 Scheduled lead #{lead_id} at {next_run.astimezone(IST).strftime('%d %b %H:%M IST')}")
    finally:
        session.close()

def sync_scheduler_with_db(bot, loop):
    from db import SessionLocal
    from models.lead import Lead
    print("🔄 Syncing scheduler with database (Smart Stagger)...")
    session = SessionLocal()
    try:
        active_leads = session.query(Lead).filter(
            ~Lead.site_status.in_(["Won", "Lost"]),
            Lead.next_followup_date.isnot(None)
        ).all()
        
        overdue_count = 0
        for lead in active_leads:
            if not scheduler.get_job(f"followup_{lead.id}"):
                stored_date = _to_aware(lead.next_followup_date)
                
                # If date is in the past, stagger current firing by 3s
                if stored_date < _utcnow():
                    delay = overdue_count * 3
                    schedule_followups(lead.id, lead.sales_exec_id, bot, loop, lead.stage, force_delay_sec=delay)
                    overdue_count += 1
                else:
                    schedule_followups(lead.id, lead.sales_exec_id, bot, loop, lead.stage)
        for job in scheduler.get_jobs():
            if job.id.startswith("followup_"):
                l_id = int(job.id.replace("followup_", ""))
                l = session.query(Lead).filter(Lead.id == l_id).first()
                if not l or l.site_status in ("Won", "Lost") or not l.next_followup_date:
                    job.remove()
    finally: session.close()
    print_scheduler_status()

def print_scheduler_status():
    from db import SessionLocal
    from models.lead import Lead
    IST = timezone(timedelta(hours=5, minutes=30))
    now = _utcnow()
    jobs = [j for j in scheduler.get_jobs() if j.id.startswith("followup_")]
    if not jobs:
        print("📭  No follow-up jobs scheduled")
        return
    print(f"\n{'─'*60}\n📅  SCHEDULED FOLLOW-UPS ({len(jobs)})\n{'─'*60}")
    session = SessionLocal()
    try:
        for job in sorted(jobs, key=lambda j: j.id):
            lead_id = int(job.id.split("_")[1]); lead = session.query(Lead).filter(Lead.id == lead_id).first()
            if lead:
                ist_str = job.next_run_time.astimezone(IST).strftime("%d %b %H:%M IST")
                print(f"  Lead #{lead_id:3} | {lead.company_name[:20]:20} | 🕐 {ist_str}")
    finally: session.close()
    print(f"{'─'*60}\n")

def reschedule_on_update(lead_id: int, chat_id: int, new_stage: str, bot, loop):
    schedule_followups(lead_id, chat_id, bot, loop, new_stage, count=1)

def send_followup_reminder(lead_id: int, chat_id: int, bot, loop, stage: str = None, count: int = 1, retry_count: int = 0):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    from db import SessionLocal
    from models.lead import Lead

    MINIAPP_BASE = (os.getenv("MINIAPP_BASE_URL") or os.getenv("WEBHOOK_URL") or "").rstrip("/")
    session = SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead or lead.site_status in ("Won", "Lost") or not lead.next_followup_date:
            _cancel_pending_jobs(lead_id); return
        IST = timezone(timedelta(hours=5, minutes=30))
        nfd_str = _to_aware(lead.next_followup_date).astimezone(IST).strftime("%d %b %H:%M IST")
        text = (
            f"📋 *Lead Follow-up:* {lead.company_name or '—'}\n"
            f"👤 Contact: {lead.client_name or '—'}\n"
            f"📞 Phone: {lead.client_phone or '—'}\n"
            f"🏗 Stage: {lead.stage or '—'}\n"
            f"📦 Material: {lead.material or '—'}\n"
            f"📐 SQ Ft: {lead.grade or '—'}\n"
            f"📊 Quantity: {lead.quantity or '—'}\n"
            f"✅ Status: {lead.site_status or '—'}\n"
            f"💬 Remarks: {lead.remarks or '—'}\n\n"
            f"_📅 Scheduled reminder · {nfd_str}_"
            + (f"\n🗺 https://www.google.com/maps?q={lead.latitude},{lead.longitude}" if lead.latitude else "")
        )

        update_url = f"{MINIAPP_BASE}/miniapp/update?lead_id={lead_id}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Update Submission", web_app=WebAppInfo(url=update_url))]])
    finally:
        session.close()

    async def _send_and_process():
        # Pre-send check
        s = SessionLocal()
        try:
            db_l = s.query(Lead).filter(Lead.id == lead_id).first()
            if not db_l or not db_l.next_followup_date or db_l.site_status in ("Won", "Lost"): return
        finally: s.close()

        # 2. Smart Jitter (0.1 to 5s) to avoid Telegram flood limits
        await asyncio.sleep(random.uniform(0.1, 5.0))
        
        try:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
            # 3. Success: Clear date in a new session
            s = SessionLocal(); 
            try:
                db_l = s.query(Lead).filter(Lead.id == lead_id).first()
                if db_l:
                    db_l.last_followup_at = _utcnow(); db_l.next_followup_date = None
                    s.commit(); print(f"✅ Sent lead #{lead_id}")
            finally: s.close()
        except Exception as e:
            print(f"❌ Failed lead #{lead_id}: {e}")
            if retry_count < 5:
                _schedule_single(lead_id, chat_id, bot, loop, stage, _utcnow()+timedelta(minutes=2), count, retry_count+1)

    asyncio.run_coroutine_threadsafe(_send_and_process(), loop)
