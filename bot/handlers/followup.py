# bot/handlers/followup.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from models.followup import FollowUp
from db import SessionLocal


async def handle_followup_response(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')  # fu_<lead_id>_<status>
    lead_id = int(parts[1])
    status = parts[2]

    ctx.user_data['fu_lead_id'] = lead_id
    ctx.user_data['fu_status'] = status

    if status == 'converted':
        await query.edit_message_text('Great! Enter order volume in m3 and date (e.g. 50 m3 / 2024-03-15)')
        return 'FU_CONVERTED_DETAILS'

    elif status == 'lost':
        keyboard = [
            [InlineKeyboardButton('Price Issue',      callback_data=f'reason_{lead_id}_price')],
            [InlineKeyboardButton('Quality Concern',  callback_data=f'reason_{lead_id}_quality')],
            [InlineKeyboardButton('Delivery Delay',   callback_data=f'reason_{lead_id}_delay')],
            [InlineKeyboardButton('Other',            callback_data=f'reason_{lead_id}_other')],
        ]
        await query.edit_message_text(
            'Reason for not converting?',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return 'FU_LOST_REASON'

    elif status == 'progress':
        await query.edit_message_text('Enter next follow-up date (YYYY-MM-DD)')
        return 'FU_NEXT_DATE'


def save_followup(lead_id: int, status: str, detail: str) -> None:
    """Persist a FollowUp row. Opens and closes its own session."""
    session = SessionLocal()
    try:
        fu = FollowUp(lead_id=lead_id, status=status, detail=detail)
        session.add(fu)
        session.commit()
    finally:
        session.close()
