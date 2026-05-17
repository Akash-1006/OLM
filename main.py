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
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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

BASE_DIR = Path(__file__).parent

# ── Build Telegram Application once (module-level singleton) ──────────────────
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(CommandHandler("newlead", start_lead))
telegram_app.add_handler(CommandHandler("start",   start_lead))
telegram_app.add_handler(CallbackQueryHandler(handle_followup_response, pattern="^fu_"))
register_admin_handlers(telegram_app)


# ── Lifespan: startup & shutdown ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ─ STARTUP ────────────────────────────────────────────────────────────────────
    Base.metadata.create_all(engine)

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print(f"\u2705 Telegram bot initialized & webhook set \u2192 {WEBHOOK_URL}/webhook")

    loop = asyncio.get_event_loop()
    app.state.bot          = telegram_app.bot
    app.state.loop         = loop
    app.state.telegram_app = telegram_app

    register_daily_digest(apscheduler, telegram_app.bot, loop)
    sync_scheduler_with_db(telegram_app.bot, loop)

    apscheduler.add_job(
        sync_scheduler_with_db,
        trigger="interval",
        hours=1,
        args=[telegram_app.bot, loop],
        id="sync_scheduler",
        replace_existing=True,
    )

    print_scheduler_status()
    print("\u2705 OLM SaaS \u2014 FastAPI ready")

    yield   # ←─ application runs here ─→

    # ─ SHUTDOWN ───────────────────────────────────────────────────────────────────
    apscheduler.shutdown(wait=False)
    await telegram_app.stop()
    await telegram_app.shutdown()
    print("\U0001f6d1 OLM SaaS \u2014 shutdown complete")


# ── FastAPI app ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="OLM SaaS",
    version="2.0.0",
    description="On-site Lead Management \u2014 multi-tenant SaaS",
    lifespan=lifespan,
)

# ── Static files ────────────────────────────────────────────────────────────────
if (BASE_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

if (BASE_DIR / "miniapp").exists():
    app.mount("/miniapp-static", StaticFiles(directory=BASE_DIR / "miniapp"), name="miniapp_static")


# ── HTML page routes ───────────────────────────────────────────────────────────
@app.get("/admin-panel", include_in_schema=False)
async def serve_admin_panel():
    """Serve the tenant admin dashboard HTML."""
    html = BASE_DIR / "admin_dashboard" / "index.html"
    if not html.exists():
        html = BASE_DIR / "static" / "admin.html"
    if not html.exists():
        return JSONResponse({"error": "Admin panel HTML not found"}, status_code=404)
    return FileResponse(html)


@app.get("/master-admin", include_in_schema=False)
async def serve_master_admin():
    """Serve the master admin HTML."""
    html = BASE_DIR / "master_admin" / "index.html"
    if not html.exists():
        return JSONResponse({"error": "Master admin HTML not found"}, status_code=404)
    return FileResponse(html)


# ── API routers ─────────────────────────────────────────────────────────────────
from routers import webhook, miniapp, admin, master_admin

app.include_router(webhook.router)
app.include_router(miniapp.router)
app.include_router(admin.router)
app.include_router(master_admin.router)


# ── Health check ────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "running", "version": "2.0.0"}


# ── Dev entrypoint ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=5001, reload=False)
