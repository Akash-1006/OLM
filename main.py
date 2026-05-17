# main.py  — FastAPI entry point (replaces Flask app.py)
"""
Replaces app.py.
All Flask routes have been migrated to FastAPI routers under routers/.

Startup order (lifespan):
  1. Create DB tables
  2. Initialize & start Telegram bot, set webhook
  3. Register daily digest cron
  4. Sync APScheduler with DB (recover active lead jobs)
  5. App is ready to serve requests

Shutdown order (lifespan exit):
  1. Stop Telegram bot
  2. Shutdown bot

The background event-loop hack (threading.Thread + run_coroutine_threadsafe)
has been REMOVED.  Bot coroutines are awaited directly in async routes and
in APScheduler jobs via asyncio.run_coroutine_threadsafe against the main
event loop which is captured once at startup.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from config import TELEGRAM_TOKEN, WEBHOOK_URL
from db import engine, Base
from bot.scheduler import (
    sync_scheduler_with_db,
    scheduler as apscheduler,
    print_scheduler_status,
)
from bot.daily_digest import register_daily_digest
from bot.handlers.lead import start_lead
from bot.handlers.followup import handle_followup_response
from bot.handlers.admin import register_admin_handlers

# Import all routers
from routers import webhook, miniapp, admin, master_admin

# ─────────────────────────────────────────────────────────────────────────────
# Build the Telegram Application (no background loop needed in FastAPI)
# ─────────────────────────────────────────────────────────────────────────────
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(CommandHandler("newlead", start_lead))
telegram_app.add_handler(CommandHandler("start", start_lead))
telegram_app.add_handler(CallbackQueryHandler(handle_followup_response, pattern="^fu_"))
register_admin_handlers(telegram_app)

# Global reference to the running event loop — shared with APScheduler jobs
_main_loop: asyncio.AbstractEventLoop | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — startup + shutdown
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _main_loop
    _main_loop = asyncio.get_running_loop()

    # 1. Create DB tables
    Base.metadata.create_all(engine)
    print("✅ Database tables verified")

    # 2. Initialize Telegram bot & set webhook
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print(f"✅ Telegram bot initialized — webhook → {WEBHOOK_URL}/webhook")

    # 3. Register daily digest cron
    register_daily_digest(apscheduler, telegram_app.bot, _main_loop)

    # 4. Sync scheduler with DB (recover any active lead jobs)
    sync_scheduler_with_db(telegram_app.bot, _main_loop)
    print_scheduler_status()

    # Hourly re-sync job (catches any leads added while server was down)
    apscheduler.add_job(
        sync_scheduler_with_db,
        trigger="interval",
        hours=1,
        args=[telegram_app.bot, _main_loop],
        id="sync_scheduler",
        replace_existing=True,
    )

    print("🚀 OLM FastAPI server ready")
    yield  # ← server runs here

    # Shutdown
    await telegram_app.stop()
    await telegram_app.shutdown()
    print("👋 Telegram bot stopped")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI application
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="OLM — On-site Lead Manager",
    version="2.0.0",
    docs_url="/docs",         # Swagger UI — disable in production if desired
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Static files (CSS, JS, images used by admin/miniapp)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Inject shared state into routers via app.state ────────────────────────────
# Routers access bot + loop via request.app.state
@app.on_event("startup")          # runs after lifespan yield — safe to read state
async def _set_app_state():       # lifespan already populated _main_loop
    app.state.telegram_app = telegram_app
    app.state.loop         = _main_loop
    app.state.scheduler    = apscheduler

# ── Include routers ───────────────────────────────────────────────────────────
app.include_router(webhook.router)       # POST /webhook
app.include_router(miniapp.router)       # /miniapp, /submit_lead, /api/*
app.include_router(admin.router)         # /admin, /admin/api/*
app.include_router(master_admin.router)  # /master-admin/*


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "running", "version": "2.0.0"}


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=5001, reload=False)
