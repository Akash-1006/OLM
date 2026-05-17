# routers/webhook.py
"""
Telegram webhook endpoint.
Receives POST /webhook from Telegram and dispatches to the bot application.
No tenant resolution needed here — the bot app is looked up by token.
"""
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from telegram import Update

router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(request: Request) -> PlainTextResponse:
    """
    Telegram calls this URL on every message/callback.
    We retrieve the correct bot application from app state (set in main.py lifespan).
    """
    telegram_app = request.app.state.telegram_app
    payload = await request.json()
    update = Update.de_json(payload, telegram_app.bot)
    await telegram_app.process_update(update)
    return PlainTextResponse("OK")
