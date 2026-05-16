from fastapi import APIRouter, Request, HTTPException
from telegram import Update
from modules.bots.orchestrator import orchestrator
import uuid
import asyncio

router = APIRouter()

@router.post("/webhook/{client_id}")
async def bot_webhook(client_id: uuid.UUID, request: Request):
    if client_id not in orchestrator.apps:
        raise HTTPException(status_code=404, detail="Bot not found for this client")

    app = orchestrator.apps[client_id]
    update_data = await request.json()
    update = Update.de_json(update_data, app.bot)

    # Process update asynchronously
    asyncio.create_task(app.process_update(update))

    return "OK"
