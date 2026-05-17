# main.py
"""
FastAPI entry point — replaces app.py.

Key changes vs old Flask app:
  - Native async: no more background thread / run_coroutine_threadsafe
  - lifespan context manager handles bot init + scheduler startup
  - Routers split by concern (webhook / miniapp / admin / master_admin)
  - Tenant-aware from the start via Depends(get_current_tenant)
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from db import engine, Base
from config import TELEGRAM_TOKEN, WEBHOOK_URL
from bot.handlers.lead import start_lead
from bot.handlers.followup import handle_followup_response
from bot.handlers.admin import register_admin_handlers
from bot.scheduler import (
    scheduler as apscheduler,
    sync_scheduler_with_db,
    print_scheduler_status,
)
from bot.daily_digest import register_daily_digest

# ── Build Telegram Application once (module-level singleton) ────────────────
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(CommandHandler("newlead", start_lead))
telegram_app.add_handler(CommandHandler("start",   start_lead))
telegram_app.add_handler(CallbackQueryHandler(handle_followup_response, pattern="^fu_"))
register_admin_handlers(telegram_app)


# ── Lifespan: startup & shutdown ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ─── STARTUP ────────────────────────────────────────────────────────────────
    # 1. Create all DB tables (idempotent)
    Base.metadata.create_all(engine)

    # 2. Initialise Telegram bot & set webhook
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print(f"✅ Telegram bot initialized & webhook set → {WEBHOOK_URL}/webhook")

    # 3. Capture the running event loop (uvicorn's loop)
    #    This replaces the old threading.Thread + asyncio.new_event_loop() hack.
    loop = asyncio.get_event_loop()

    # 4. Store references on app.state so routers can access them
    app.state.bot         = telegram_app.bot
    app.state.loop        = loop
    app.state.telegram_app = telegram_app

    # 5. Register daily digest cron
    register_daily_digest(apscheduler, telegram_app.bot, loop)

    # 6. Recover any scheduled follow-ups from DB
    sync_scheduler_with_db(telegram_app.bot, loop)

    # 7. Hourly re-sync to catch any missed leads
    apscheduler.add_job(
        sync_scheduler_with_db,
        trigger="interval",
        hours=1,
        args=[telegram_app.bot, loop],
        id="sync_scheduler",
        replace_existing=True,
    )

    print_scheduler_status()
    print("✅ OLM SaaS — FastAPI ready")

    yield   # ←── application runs here ──→

    # ─── SHUTDOWN ───────────────────────────────────────────────────────────────
    apscheduler.shutdown(wait=False)
    await telegram_app.stop()
    await telegram_app.shutdown()
    print("🛑 OLM SaaS — shutdown complete")


# ── FastAPI app ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="OLM SaaS",
    version="2.0.0",
    description="On-site Lead Management — multi-tenant SaaS",
    lifespan=lifespan,
)

# ── Mount routers ──────────────────────────────────────────────────────────────────
from routers import webhook, miniapp, admin, master_admin

app.include_router(webhook.router)
app.include_router(miniapp.router)
app.include_router(admin.router)
app.include_router(master_admin.router)


# ── Health check ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "running", "version": "2.0.0"}


# ── Dev entrypoint ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=5001, reload=False)
