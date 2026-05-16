import asyncio
from telegram.ext import Application
from typing import Dict
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from modules.tenants.models import Client
from core.database import AsyncSessionLocal

class BotOrchestrator:
    def __init__(self):
        self.apps: Dict[uuid.UUID, Application] = {}

    async def load_client_bot(self, client: Client):
        if client.id in self.apps:
            await self.apps[client.id].stop()
            await self.apps[client.id].shutdown()

        # Build the PTB Application
        app = Application.builder().token(client.bot_token).build()

        # Add common handlers here (e.g., /start)
        from modules.bots.handlers.lead import start_lead
        from telegram.ext import CommandHandler
        app.add_handler(CommandHandler("start", start_lead))
        app.add_handler(CommandHandler("newlead", start_lead))

        await app.initialize()
        await app.start()
        self.apps[client.id] = app
        print(f"✅ Bot initialized for client: {client.name} ({client.id})")

    async def load_all_active_bots(self):
        async with AsyncSessionLocal() as db:
            stmt = select(Client).where(Client.status == "active")
            result = await db.execute(stmt)
            clients = result.scalars().all()

            for client in clients:
                try:
                    await self.load_client_bot(client)
                except Exception as e:
                    print(f"❌ Failed to load bot for {client.name}: {e}")

    async def stop_all(self):
        for client_id, app in self.apps.items():
            await app.stop()
            await app.shutdown()
        self.apps.clear()

orchestrator = BotOrchestrator()
