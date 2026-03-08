import asyncio
import logging
from scripts.bot_utils import send_message, send_photo

logger = logging.getLogger(__name__)

bot_loop = None

def set_bot_loop(loop):
    global bot_loop
    bot_loop = loop

def kirim_notifikasi_sinkron(pesan):
    if bot_loop is not None:
        asyncio.run_coroutine_threadsafe(send_message(pesan), bot_loop)
    else:
        logger.error("❌ bot_loop belum siap, pesan tidak terkirim: %s", pesan)

def kirim_foto_sinkron(photo_bytes, caption=''):
    if bot_loop is not None:
        asyncio.run_coroutine_threadsafe(send_photo(photo_bytes, caption), bot_loop)
    else:
        logger.error("❌ bot_loop belum siap, foto tidak terkirim")