# routers/webhook.py
"""
Telegram webhook endpoint.

POST /webhook  ──  receives updates from Telegram and processes them
               via the telegram_app Application object stored on app.state.
"""
from fastapi import APIRouter, Request
from fastapi.responses import Response
from telegram import Update

router = APIRouter(tags=["webhook"])


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive a Telegram update and dispatch it through python-telegram-bot."""
    telegram_app = request.app.state.telegram_app
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    # process_update is a coroutine — await directly (no thread bridging needed)
    await telegram_app.process_update(update)
    return Response(content="OK", status_code=200)
