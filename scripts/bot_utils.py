# scripts/bot_utils.py
import asyncio
import logging
from telegram import Update
from telegram.ext import Application

logger = logging.getLogger(__name__)

_app = None

def set_application(app):
    global _app
    _app = app

async def send_message(text, chat_id=None):
    if _app is None:
        logger.error("ERROR: Aplikasi bot belum di-set")
        return
    if chat_id is None:
        from scripts.telegram_bot import CHAT_ID
        chat_id = CHAT_ID
    await _app.bot.send_message(chat_id=chat_id, text=text)

async def send_photo(photo_bytes, caption='', chat_id=None):
    if _app is None:
        logger.error("ERROR: Aplikasi bot belum di-set")
        return
    if chat_id is None:
        from scripts.telegram_bot import CHAT_ID
        chat_id = CHAT_ID
    await _app.bot.send_photo(chat_id=chat_id, photo=photo_bytes, caption=caption)

async def send_long_message(update: Update, text: str):
    max_length = 4096
    if len(text) <= max_length:
        await update.message.reply_text(text)
    else:
        parts = []
        current_part = ""
        for line in text.split('\n'):
            if len(current_part) + len(line) + 1 <= max_length:
                current_part += line + '\n'
            else:
                parts.append(current_part)
                current_part = line + '\n'
        if current_part:
            parts.append(current_part)
        for i, part in enumerate(parts):
            await update.message.reply_text(f"*Bagian {i+1}/{len(parts)}*\n{part}")