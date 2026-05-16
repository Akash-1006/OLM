from apscheduler.schedulers.asyncio import AsyncIOScheduler
from modules.bots.orchestrator import orchestrator
from core.database import AsyncSessionLocal
from sqlalchemy import select
from modules.leads.models import Lead
from datetime import datetime, timezone
import asyncio

scheduler = AsyncIOScheduler(timezone=timezone.utc)

async def send_followup_reminder(lead_id: int):
    async with AsyncSessionLocal() as db:
        stmt = select(Lead).where(Lead.id == lead_id)
        lead = (await db.execute(stmt)).scalar_one_or_none()

        if not lead or lead.site_status in ["Won", "Lost"]:
            return

        app = orchestrator.apps.get(lead.client_id)
        if not app:
            return

        message = f"🔔 *Follow-up Reminder*\n\n🏢 *{lead.company_name}*\n👤 {lead.sales_exec_name}\n📍 Status: {lead.site_status}"
        try:
            await app.bot.send_message(
                chat_id=lead.sales_exec_id,
                text=message,
                parse_mode="Markdown"
            )
            # Update last_followup_at
            lead.last_followup_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as e:
            print(f"❌ Failed to send reminder: {e}")

async def start_scheduler():
    scheduler.start()
    print("⏰ Scheduler started")

async def stop_scheduler():
    scheduler.shutdown()
