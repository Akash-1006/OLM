# bot/handlers/lead.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from config import WEBHOOK_URL

MINI_APP_URL = f"{WEBHOOK_URL}/miniapp"

async def start_lead(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /newlead — sends a button that opens the Mini App lead form inside Telegram.
    No ConversationHandler needed — the form handles all input.
    """
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="📋 Open Lead Form",
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
    ]])
    await update.message.reply_text(
        "Tap below to open the lead capture form:",
        reply_markup=keyboard
    )