# scripts/telegram_bot.py
import sys
import os
import asyncio
import concurrent.futures
import time
import psutil
from datetime import datetime, timedelta
import logging
import io
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scripts.historical_investiny import update_all_historical
from scripts.ml_train_advanced import train_advanced_model
from scripts.watchlist import load_watchlist
from scripts.fundamental import update_all_fundamental
from scripts.training_queue import get_training_queue


# Tambahkan path folder utama ke sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
from scripts.trade_executor import TradeExecutor

# Setup logger
logger = logging.getLogger(__name__)

logger.info("0: Memulai telegram_bot.py")
logger.info("1: import sys OK")
logger.info("2: import os OK")
logger.info("3: import asyncio OK")
logger.info("4: import concurrent.futures OK")
logger.info("5: import time OK")
logger.info("6: import psutil OK")
logger.info("7: import datetime OK")
logger.info("8: import logging OK")
logger.info("9: import io OK")
logger.info("10: import sqlite3 OK")
logger.info("11: import pandas OK")
logger.info("12: import numpy OK")
logger.info("13: import matplotlib OK")
logger.info("14: sys.path.append OK")
logger.info("15: from telegram import Update OK")
logger.info("16: from telegram.ext import Application, CommandHandler, ContextTypes OK")
logger.info("17: from telegram.request import HTTPXRequest OK")
logger.info("18: from dotenv import load_dotenv OK")

logger.info("19: Mulai import dari modul internal...")
try:
    from scripts.ai_validator_v2 import client, MODEL_NAME
    logger.info("20: import ai_validator_v2 OK")
except Exception as e:
    logger.error("20: ERROR import ai_validator_v2: %s", e)
    raise

try:
    from scripts.sentiment import get_news_sentiment
    logger.info("21: import sentiment OK")
except Exception as e:
    logger.error("21: ERROR import sentiment: %s", e)
    raise

try:
    from scripts.top_stocks import format_top_stocks
    logger.info("22: import top_stocks OK")
except Exception as e:
    logger.error("22: ERROR import top_stocks: %s", e)
    raise

try:
    from scripts.backtest import BacktestEngine
    logger.info("23: import backtest OK")
except Exception as e:
    logger.error("23: ERROR import backtest: %s", e)
    raise

try:
    from scripts.analisis_adaptif import ambil_data_dari_db, tambah_indikator
    logger.info("24: import analisis_adaptif OK")
except Exception as e:
    logger.error("24: ERROR import analisis_adaptif: %s", e)
    raise

try:
    from scripts.bot_utils import send_long_message, send_message, send_photo, set_application
    logger.info("25: import bot_utils OK")
except Exception as e:
    logger.error("25: ERROR import bot_utils: %s", e)
    raise

try:
    from scripts.watchlist import add_to_watchlist, remove_from_watchlist, format_watchlist, update_target, update_stop
    logger.info("26: import watchlist OK")
except Exception as e:
    logger.error("26: ERROR import watchlist: %s", e)
    raise

try:
    from scripts.multi_tf import get_tf_analysis_v2, format_tf_analysis_v2
    logger.info("27: import multi_tf OK")
except Exception as e:
    logger.error("27: ERROR import multi_tf: %s", e)
    raise

try:
    from scripts.screener import get_screener_results, format_screener
    logger.info("28: import screener OK")
except Exception as e:
    logger.error("28: ERROR import screener: %s", e)
    raise

try:
    from scripts.formatters import format_rupiah, format_persen, format_volume, format_rsi
    logger.info("29: import formatters OK")
except Exception as e:
    logger.error("29: ERROR import formatters: %s", e)
    raise

try:
    from scripts.economic_calendar import get_economic_calendar, format_calendar
    logger.info("30: import economic_calendar OK")
except Exception as e:
    logger.error("30: ERROR import economic_calendar: %s", e)
    raise

try:
    from scripts.circuit_breaker import get_state_info, set_daily_loss_cap
    logger.info("31: import circuit_breaker OK")
except Exception as e:
    logger.error("31: ERROR import circuit_breaker: %s", e)
    raise

try:
    from scripts.walk_forward import walk_forward, robustness_test
    logger.info("32: import walk_forward OK")
except Exception as e:
    logger.error("32: ERROR import walk_forward: %s", e)
    raise

try:
    from scripts.trade_journal import get_journal_summary, get_recent_trades
    logger.info("33: import trade_journal OK")
except Exception as e:
    logger.error("33: ERROR import trade_journal: %s", e)
    raise

try:
    from scripts.paper_config import toggle_paper_mode, reset_paper_balance, load_config
    logger.info("34: import paper_config OK")
except Exception as e:
    logger.error("34: ERROR import paper_config: %s", e)
    raise

try:
    from scripts.fundamental import enrich_with_fundamental, fundamental_score
    logger.info("35: import fundamental OK")
except Exception as e:
    logger.error("35: ERROR import fundamental: %s", e)
    raise

try:
    from scripts.cluster_tracker import get_tracker
    logger.info("36: import cluster_tracker OK")
except Exception as e:
    logger.error("36: ERROR import cluster_tracker: %s", e)
    raise

logger.info("37: Semua import internal selesai")

load_dotenv()
logger.info("38: load_dotenv OK")
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
logger.info("39: TELEGRAM_TOKEN: %s", TOKEN[:5] + "..." if TOKEN else "Tidak ditemukan")

request = HTTPXRequest(
    connection_pool_size=8,
    read_timeout=30.0,
    write_timeout=30.0,
    connect_timeout=30.0,
    pool_timeout=30.0
)
logger.info("40: HTTPXRequest dibuat")

# 👉 BUAT APLIKASI TERLEBIH DAHULU
application = Application.builder().token(TOKEN).request(request).build()
logger.info("41: Application dibuat")

# Set application untuk bot_utils
set_application(application)
logger.info("42: set_application OK")

# 👉 BARU DEFINISIKAN FUNGSI GETTER
def get_application():
    """Mengembalikan objek Application yang sudah dibuat."""
    return application

# ======================================================================
# HANDLER /start
# ======================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Handler /start dipanggil")
    welcome_msg = (
        "🤖 *Selamat datang di Bot Trading Saham Indonesia!*\n\n"
        "Saya adalah asisten analisis saham yang siap membantu Anda.\n"
        "Ketik /help untuk melihat daftar perintah yang tersedia."
    )
    await update.message.reply_text(welcome_msg)

# ======================================================================
# HANDLER /help
# ======================================================================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📚 *DAFTAR PERINTAH BOT TRADING*

🔹 *Analisis & Data*
/tanya <kode> <pertanyaan> → Analisis teknikal + sentimen berita + jawaban AI
/jelas <kode> → Info cepat: harga, RSI, support/resistance, data fundamental
/banding <kode1> <kode2> → Perbandingan teknikal + rekomendasi AI
/top → Saham dengan performa terbaik/terburuk (1H, 1M, 1B)
/screener [filter] → Screening saham (all, oversold, overbought, volume, golden, death)
/tf <kode> [arah] → Analisis multi-timeframe daily, weekly, monthly (arah: buy/sell)
/atr <kode> → Hitung ATR, rekomendasi stop loss dan target profit
/fundamental <kode> → Tampilkan data fundamental lengkap saham
/jelas_multi
/tf_multi
/agent_multi
/train_status

🔹 *Watchlist & Manajemen*
/watchlist → Tampilkan daftar pantauan
/watchlist_add <kode> [target] [stop] → Tambah saham ke watchlist
/watchlist_remove <kode> → Hapus saham dari watchlist
/watchlist_target <kode> <target> → Update target harga
/watchlist_stop <kode> <stop> → Update stop loss

🔹 *Trading & Eksekusi*
/paper → Status dan saldo paper trading
/paper_toggle → Aktif/nonaktifkan mode paper
/paper_reset → Reset saldo paper ke Rp 100.000.000
/backtest <kode> → Simulasi trading historis (backtesting)
/walkforward <kode> → Walk-forward analysis
/robust <kode> → Robustness test parameter
/optimize <kode> → Optimasi parameter strategi (berdasarkan walk-forward)
/risk → Status loss harian/bulanan, cooldown
/set_cap <persen> → Ubah batas loss harian
/journal [hari] → Ringkasan performa trading (default 7 hari)
/evaluasi → Laporan mingguan (grafik equity + statistik + evaluasi AI)

🔹 *Machine Learning & Multi-Agent*
/retrain <kode> → Latih ulang model ML XGBoost untuk saham tertentu
/train_all → Latih model ML untuk semua saham di watchlist (background)
/mlreport <kode> → Laporan performa model ML (akurasi, parameter)
/mlstatus → Status model ML yang telah dilatih
/train_regime → Latih ulang model GMM regime classifier
/regime <kode> → Tampilkan regime pasar (GMM) untuk saham tertentu
/agent <kode> → Tampilkan sinyal dari multi-agent system
/lstm_status → Status model LSTM (sedang training/tersedia)
/weights → Tampilkan bobot agent saat ini
/rlstatus → Status RL orchestrator (Q-table)
/dqnstatus → Status DQN agent (epsilon, memory, dll.)

🔹 *Klaster & Sentimen Berita*
/clusters → Tampilkan klaster saham dari berita
/clustersent → Rekomendasi berdasarkan sentimen klaster
/cooccur <kode> → Tampilkan saham yang sering muncul bersama
/clusters_update → Update klaster berita secara manual
/news_sentiment <kode> → Analisis sentimen berita terkini dari Google News
/sectors → Tampilkan sektor terkuat berdasarkan performa
/strategies → Tampilkan 5 strategi terbaik hasil generator

🔹 *Data Historis & Fundamental*
/update_fundamental_all → Update data fundamental dari StockBit (default: watchlist)
/update_historical [all] → Update data historis dari Yahoo Finance (default: watchlist)
/update_all_stocks → Update semua saham di database (dengan jeda 5 detik)
/import_status → Tanggal data terakhir setiap saham
/export <kode> → Download data saham sebagai CSV
/evaluate_agents
/datacheck <kode>

🔹 *Data Ekonomi*
/update_econ → Update data ekonomi dari FRED
/update_econid → Update data ekonomi Indonesia (World Bank + libur nasional)
/econid → Tampilkan data ekonomi Indonesia terkini
/econrisk → Status risiko ekonomi global
/calendar → Kalender ekonomi 7 hari ke depan

🔹 *Monitoring & Debugging*
/status → Info database, bot, dan sistem
/errors → Tampilkan 10 error terbaru dari log
/lstm_tuning_log → Tampilkan progres tuning LSTM terbaru
/training_status → Status training model (LSTM/XGBoost) yang sedang berjalan
/help → Tampilkan pesan ini

💡 *Tips:* 
• Kode saham bisa dengan atau tanpa .JK (contoh: BBCA atau BBCA.JK)
• Untuk perintah yang memerlukan parameter, gunakan spasi sebagai pemisah
• Proses training LSTM berjalan di background – gunakan /lstm_status untuk cek progres
• Update data historis untuk semua saham memakan waktu ~1 jam, jalankan saat komputer tidak digunakan
    """
    await send_long_message(update, help_text)

# ======================================================================
# HANDLER /status
# ======================================================================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect('data/saham.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT Symbol) FROM saham")
        total_symbols = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM saham")
        total_rows = cursor.fetchone()[0]
        conn.close()

        process = psutil.Process()
        memory_usage = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent(interval=0.1)

        status_text = f"""
📊 *STATUS BOT TRADING*

🗄️ *Database*
• Total saham: {total_symbols} emiten
• Total baris data: {total_rows:,} baris
• Ukuran file: {os.path.getsize('data/saham.db') / 1024 / 1024:.2f} MB

🖥️ *Sistem*
• RAM: {memory_usage:.1f} MB
• CPU: {cpu_percent:.1f}%
• Python: {os.sys.version.split()[0]}

🤖 *Bot Telegram*
• Model AI: {MODEL_NAME}
• Status: 🟢 Online

📅 *Update terakhir*: {datetime.now().strftime('%d %b %Y %H:%M')}
        """
        await update.message.reply_text(status_text)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ======================================================================
# HANDLER /top
# ======================================================================
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = format_top_stocks()
        await send_long_message(update, text)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ======================================================================
# HANDLER /tanya
# ======================================================================
async def tanya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Format: /tanya <kode> <pertanyaan>\nContoh: /tanya BBCA kenapa turun?")
        return

    raw_symbol = context.args[0].upper()
    question = ' '.join(context.args[1:])

    if not raw_symbol.endswith('.JK'):
        symbol_with_jk = raw_symbol + '.JK'
    else:
        symbol_with_jk = raw_symbol

    df = ambil_data_dari_db(symbol_with_jk)
    symbol_used = symbol_with_jk

    if df is None and raw_symbol != symbol_with_jk:
        df = ambil_data_dari_db(raw_symbol)
        if df is not None:
            symbol_used = raw_symbol

    if df is None or len(df) < 10:
        await update.message.reply_text(f"Data untuk {raw_symbol} tidak cukup atau tidak tersedia.")
        return

    df = tambah_indikator(df)
    latest = df.iloc[-1]

    prompt = f"""
    Saham: {symbol_used}
    Data terkini ({latest['Date'].strftime('%Y-%m-%d')}):
    - Harga: {latest['Close']:.2f}
    - RSI: {latest['RSI']:.2f}
    - MACD: {latest['MACD']:.2f}, Signal: {latest['MACD_signal']:.2f}
    - EMA20: {latest['EMA20']:.2f}, EMA50: {latest['EMA50']:.2f}
    - Volume: {latest['Volume']:.0f} (rata-rata 20 hari: {latest['Volume_MA20']:.0f})
    Pertanyaan: {question}
    Jawab dalam Bahasa Indonesia, singkat dan jelas. Berikan analisis berdasarkan data teknikal.
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            await send_long_message(update, response.choices[0].message.content)

            sentimen = get_news_sentiment(symbol_used)
            await update.message.reply_text(f"📰 *Sentimen Berita:*\n{sentimen}")
            break
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                await update.message.reply_text("⚠️ Server AI sibuk, mencoba lagi...")
                await asyncio.sleep(5)
            else:
                await update.message.reply_text(f"Error: {e}")
                break

# ======================================================================
# HANDLER /jelas
# ======================================================================
async def jelas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 1:
            await update.message.reply_text("❌ Format: /jelas <kode>\nContoh: `/jelas BBCA`")
            return

        raw_symbol = context.args[0].upper()
        if not raw_symbol.endswith('.JK'):
            symbol = raw_symbol + '.JK'
        else:
            symbol = raw_symbol

        from scripts.analisis_adaptif import ambil_data_dari_db, tambah_indikator
        from scripts.formatters import format_rupiah, format_volume
        from scripts.fundamental import enrich_with_fundamental, fundamental_score

        # Ambil data 100 hari terakhir
        df = ambil_data_dari_db(symbol, hari=100)
        logger.info(f"Data untuk {symbol}: {len(df) if df is not None else 'None'} baris")
        if df is None or len(df) < 10:
            # coba tanpa .JK
            alt_symbol = raw_symbol if raw_symbol.endswith('.JK') else raw_symbol
            df = ambil_data_dari_db(alt_symbol, hari=100)
            logger.info(f"Data untuk {alt_symbol}: {len(df) if df is not None else 'None'} baris")
            if df is None or len(df) < 10:
                await update.message.reply_text(f"❌ Data untuk {raw_symbol} tidak cukup (minimal 10 baris).")
                return
            else:
                symbol = alt_symbol

        # Tambah indikator
        try:
            df = tambah_indikator(df)
        except Exception as e:
            logger.exception(f"Error tambah indikator: {e}")
            await update.message.reply_text(f"❌ Gagal menghitung indikator: {e}")
            return

        # Ambil data terbaru
        latest = df.iloc[-1]

        # Periksa apakah ada NaN di baris terakhir
        if latest.isnull().any():
            nan_cols = latest[latest.isnull()].index.tolist()
            logger.warning(f"Ada NaN di data terakhir {symbol}: {nan_cols}")
            await update.message.reply_text(f"⚠️ Data terakhir mengandung nilai kosong: {nan_cols}. Beberapa indikator mungkin tidak tersedia.")

        # Hitung support dan resistance dari 20 hari terakhir
        recent_low = df['Low'].tail(20).min()
        recent_high = df['High'].tail(20).max()

        # Kondisi RSI
        if pd.isna(latest.get('RSI')):
            kondisi = "RSI tidak tersedia"
        elif latest['RSI'] < 30:
            kondisi = "oversold (potensi beli)"
        elif latest['RSI'] > 70:
            kondisi = "overbought (potensi jual)"
        else:
            kondisi = "netral"

        # Format tanggal dengan aman
        try:
            date_val = latest['Date']
            if pd.isna(date_val):
                date_str = "Tanggal tidak tersedia"
            else:
                date_str = date_val.strftime('%d %b %Y')
        except (AttributeError, TypeError):
            date_str = str(latest.get('Date', 'N/A'))

        # Buat pesan
        msg = f"""
📈 *Analisis Cepat {symbol}*
🗓️ {date_str}

💵 Harga: {format_rupiah(latest.get('Close', 0))}
📊 RSI: {latest.get('RSI', 0):.1f} ({kondisi})
📉 EMA20: {format_rupiah(latest.get('EMA20', 0))} | EMA50: {format_rupiah(latest.get('EMA50', 0))}
📈 ADX: {latest.get('ADX', 0):.1f} | Volume: {format_volume(latest.get('Volume', 0))}
🔝 Resistance: {format_rupiah(recent_high)}
🔻 Support: {format_rupiah(recent_low)}
        """

        # Ambil data fundamental
        fundamental = enrich_with_fundamental(symbol)
        if fundamental:
            fund_score, fund_reason = fundamental_score(fundamental)
            msg += f"""
📊 *Fundamental*
PER: {fundamental.get('per', 0):.1f}x | PBV: {fundamental.get('pbv', 0):.2f}x
ROE: {fundamental.get('roe', 0):.1f}% | DER: {fundamental.get('der', 0):.2f}x
Dividen: {fundamental.get('dividend_yield', 0):.1f}%
Skor Fundamental: {fund_score}
            """

        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception("Error in jelas handler")
        await update.message.reply_text(f"❌ Terjadi error: {str(e)}")

# ======================================================================
# HANDLER /screener
# ======================================================================
async def screener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Tentukan filter berdasarkan argumen
        if len(context.args) == 0:
            filter_type = 'all'
            filter_name = 'SEMUA'
            max_results = 50
        else:
            first = context.args[0].lower()
            if first == 'oversold':
                filter_type = 'oversold'
                filter_name = 'OVERSOLD'
                max_results = 20
            elif first == 'overbought':
                filter_type = 'overbought'
                filter_name = 'OVERBOUGHT'
                max_results = 20
            elif first == 'volume':
                filter_type = 'volume_spike'
                filter_name = 'VOLUME SPIKE'
                max_results = 20
            elif first == 'golden':
                filter_type = 'golden_cross'
                filter_name = 'EMA GOLDEN CROSS'
                max_results = 20
            elif first == 'death':
                filter_type = 'death_cross'
                filter_name = 'EMA DEATH CROSS'
                max_results = 20
            else:
                await update.message.reply_text("❌ Filter tidak dikenal. Gunakan: oversold, overbought, volume, golden, death")
                return

        # Kirim pesan bahwa proses dimulai
        await update.message.reply_text(f"🔍 Menjalankan screener {filter_name}... (mohon tunggu)")

        # Panggil fungsi screener (mengembalikan semua hasil)
        results = get_screener_results(filter_type, None, 'score', True)
        total = len(results) if results else 0

        if results is None:
            await update.message.reply_text("❌ Gagal mendapatkan hasil screener.")
            return

        if total == 0:
            await update.message.reply_text(f"🔍 *Screener: {filter_name}*\n\nTidak ada saham yang memenuhi kriteria.")
            return

        # Batasi jumlah hasil yang ditampilkan
        if total > max_results:
            results = results[:max_results]
            info = f"\n\n📊 *Menampilkan {max_results} dari {total} saham*"
        else:
            info = ""

        # Format hasil
        text = format_screener(results, filter_name, info)

        # Kirim hasil, potong jika terlalu panjang
        if len(text) <= 4096:
            await update.message.reply_text(text)
        else:
            parts = []
            current = ""
            for line in text.split('\n'):
                if len(current) + len(line) + 1 <= 4000:
                    current += line + '\n'
                else:
                    parts.append(current)
                    current = line + '\n'
            if current:
                parts.append(current)

            for i, part in enumerate(parts):
                await update.message.reply_text(f"*Bagian {i+1}/{len(parts)}*\n{part}")

    except Exception as e:
        logging.exception("Error in screener handler")
        await update.message.reply_text(f"❌ Terjadi error: {e}")

# ======================================================================
# HANDLER /watchlist
# ======================================================================
async def watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = format_watchlist()
    await send_long_message(update, text)

async def watchlist_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /watchlist_add <kode> [target] [stop]")
        return

    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'

    target = None
    stop = None
    if len(context.args) >= 2:
        try:
            target = float(context.args[1])
        except:
            pass
    if len(context.args) >= 3:
        try:
            stop = float(context.args[2])
        except:
            pass

    add_to_watchlist(symbol, target, stop)
    await update.message.reply_text(f"✅ {symbol} ditambahkan ke watchlist.")

async def watchlist_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /watchlist_remove <kode>")
        return

    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'

    remove_from_watchlist(symbol)
    await update.message.reply_text(f"✅ {symbol} dihapus dari watchlist.")

async def watchlist_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format: /watchlist_target <kode> <target>\n"
            "Contoh: /watchlist_target BBCA 7500"
        )
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'
    try:
        target = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Target harus berupa angka.")
        return
    if update_target(symbol, target):
        await update.message.reply_text(f"✅ Target {symbol} diupdate ke {format_rupiah(target)}")
    else:
        await update.message.reply_text(f"❌ {symbol} tidak ditemukan di watchlist.")

async def watchlist_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format: /watchlist_stop <kode> <stop>\n"
            "Contoh: /watchlist_stop BBCA 7000"
        )
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'
    try:
        stop = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Stop harus berupa angka.")
        return
    if update_stop(symbol, stop):
        await update.message.reply_text(f"✅ Stop {symbol} diupdate ke {format_rupiah(stop)}")
    else:
        await update.message.reply_text(f"❌ {symbol} tidak ditemukan di watchlist.")

# ======================================================================
# HANDLER /tf
# ======================================================================
async def tf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ Format: /tf <kode> [arah]\n"
            "Contoh: /tf BBCA buy\n"
            "Arah opsional: buy atau sell (default buy)"
        )
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'

    target_dir = 'buy'
    if len(context.args) >= 2 and context.args[1].lower() in ['buy', 'sell']:
        target_dir = context.args[1].lower()

    await update.message.reply_text(f"⏳ Menganalisis multi-timeframe untuk {symbol} (arah: {target_dir})...")

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result, error = await loop.run_in_executor(pool, get_tf_analysis_v2, symbol, target_dir)

    if error:
        await update.message.reply_text(f"❌ {error}")
        return
    if result is None:
        await update.message.reply_text("❌ Gagal mendapatkan analisis.")
        return

    text = format_tf_analysis_v2(result)
    await send_long_message(update, text)

# ======================================================================
# HANDLER /atr - Menghitung ATR dan rekomendasi stop loss / target
# ======================================================================
async def atr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Format: /atr <kode>
    Contoh: /atr BBCA
    Menampilkan nilai ATR terkini serta rekomendasi stop loss dan target profit.
    """
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ Format: /atr <kode>\n"
            "Contoh: /atr BBCA"
        )
        return

    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'

    from scripts.data_utils import ambil_data_dari_db, tambah_indikator
    from scripts.formatters import format_rupiah

    # Ambil data historis (minimal 14 hari untuk ATR)
    df = ambil_data_dari_db(symbol, hari=50)
    if df is None or len(df) < 14:
        await update.message.reply_text(f"❌ Data untuk {symbol} tidak cukup (minimal 14 hari).")
        return

    # Hitung indikator
    df = tambah_indikator(df)
    latest = df.iloc[-1]

    entry = latest['Close']
    atr = latest['ATR']

    # Hitung stop loss dan target berdasarkan ATR (multiplier default)
    stop_loss = entry - 1.5 * atr
    target1 = entry + 1.5 * atr
    target2 = entry + 2.5 * atr
    target3 = entry + 3.5 * atr

    # Persentase untuk informasi tambahan
    stop_loss_pct = (stop_loss / entry - 1) * 100
    target1_pct = (target1 / entry - 1) * 100
    target2_pct = (target2 / entry - 1) * 100
    target3_pct = (target3 / entry - 1) * 100

    msg = (
        f"📊 *ATR Analysis: {symbol}*\n"
        f"Harga Terkini: {format_rupiah(entry)}\n"
        f"ATR (14 hari): {format_rupiah(atr)} ({atr/entry*100:.2f}% dari harga)\n\n"
        f"🛑 *Stop Loss* (1.5×ATR): {format_rupiah(stop_loss)} ({stop_loss_pct:+.2f}%)\n\n"
        f"🎯 *Target Profit*\n"
        f"• Level 1 (1.5×ATR): {format_rupiah(target1)} ({target1_pct:+.2f}%)\n"
        f"• Level 2 (2.5×ATR): {format_rupiah(target2)} ({target2_pct:+.2f}%)\n"
        f"• Level 3 (3.5×ATR): {format_rupiah(target3)} ({target3_pct:+.2f}%)\n\n"
        f"_Rekomendasi berdasarkan ATR, sesuaikan dengan strategi Anda._"
    )

    await update.message.reply_text(msg)

# ======================================================================
# HANDLER /backtest
# ======================================================================
def run_backtest_sync(symbol):
    try:
        df = ambil_data_dari_db(symbol, hari=100)
        if df is None or len(df) < 30:
            return None, "Data tidak cukup (minimal 30 hari)"
        df = tambah_indikator(df)
        engine = BacktestEngine()
        equity, trades = engine.run(df, symbol)
        metrics = engine.calculate_metrics(equity, trades)
        chart = engine.get_equity_chart(equity, symbol)
        return (equity, trades, metrics, chart), None
    except Exception as e:
        return None, str(e)

async def backtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /backtest <kode>\nContoh: `/backtest BBCA`")
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'

    await update.message.reply_text(f"⏳ Menjalankan backtest untuk {symbol}...")

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result, error = await loop.run_in_executor(pool, run_backtest_sync, symbol)

    if error:
        await update.message.reply_text(f"❌ Error: {error}")
        return
    if result is None:
        await update.message.reply_text("❌ Gagal menjalankan backtest.")
        return

    equity, trades, metrics, chart = result

    summary = f"📊 *Backtest {symbol}*\n"
    for k, v in metrics.items():
        if isinstance(v, float):
            summary += f"• {k}: {v:.2f}\n"
        else:
            summary += f"• {k}: {v}\n"
    summary += f"\n📈 Total trades: {len(trades)}"

    await update.message.reply_photo(photo=chart, caption=summary)

    if trades:
        last_trades = trades[-5:]
        text = "📋 *5 Trade terakhir:*\n"
        for t in last_trades:
            entry = t['entry_date'].strftime('%d/%m') if hasattr(t['entry_date'], 'strftime') else str(t['entry_date'])
            exit_ = t['exit_date'].strftime('%d/%m') if hasattr(t['exit_date'], 'strftime') else str(t['exit_date'])
            pnl = format_persen(t['pnl_pct'])
            text += f"• {entry} – {exit_}: {pnl}\n"
        await update.message.reply_text(text)

# ======================================================================
# HANDLER /evaluasi
# ======================================================================
async def evaluasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kirim equity curve
    buf = await send_equity_chart(update)
    if buf:
        await update.message.reply_photo(photo=buf, caption="📈 Equity Curve (Closed Trades)")
    else:
        await update.message.reply_text("Belum ada closed trade untuk ditampilkan.")

    summary = get_journal_summary(30)
    text = f"📊 *Ringkasan 30 Hari*\n"
    text += f"Total Trades: {summary['total_trades']}\n"
    text += f"Total PnL: Rp {summary['total_pnl']:,.0f}\n"
    text += f"Win Rate: {summary['win_rate']:.1f}%\n"
    if summary['open_positions']:
        text += f"Posisi Terbuka: {len(summary['open_positions'])}"
    await update.message.reply_text(text)

async def send_equity_chart(update: Update, days=30):
    conn = sqlite3.connect('data/saham.db')
    df = pd.read_sql("SELECT exit_date, pnl FROM trade_journal WHERE status='closed' AND pnl IS NOT NULL ORDER BY exit_date", conn)
    conn.close()
    if df.empty:
        return None
    df['exit_date'] = pd.to_datetime(df['exit_date'])
    df['cum_pnl'] = df['pnl'].cumsum()
    plt.figure(figsize=(10,5))
    plt.plot(df['exit_date'], df['cum_pnl'], marker='o', linestyle='-')
    plt.title('Equity Curve (Closed Trades)')
    plt.xlabel('Tanggal')
    plt.ylabel('Akumulasi PnL (Rp)')
    plt.grid(True)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

# ======================================================================
# HANDLER /banding
# ======================================================================
async def banding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Format: /banding <kode1> <kode2>\nContoh: /banding BBCA BBRI")
        return

    symbol1_raw = context.args[0].upper()
    symbol2_raw = context.args[1].upper()

    symbol1 = symbol1_raw if symbol1_raw.endswith('.JK') else symbol1_raw + '.JK'
    symbol2 = symbol2_raw if symbol2_raw.endswith('.JK') else symbol2_raw + '.JK'

    df1 = ambil_data_dari_db(symbol1)
    df2 = ambil_data_dari_db(symbol2)

    if df1 is None and symbol1 != symbol1_raw:
        df1 = ambil_data_dari_db(symbol1_raw)
        if df1 is not None:
            symbol1 = symbol1_raw
    if df2 is None and symbol2 != symbol2_raw:
        df2 = ambil_data_dari_db(symbol2_raw)
        if df2 is not None:
            symbol2 = symbol2_raw

    if df1 is None or len(df1) < 10:
        await update.message.reply_text(f"Data untuk {symbol1_raw} tidak cukup.")
        return
    if df2 is None or len(df2) < 10:
        await update.message.reply_text(f"Data untuk {symbol2_raw} tidak cukup.")
        return

    df1 = tambah_indikator(df1)
    df2 = tambah_indikator(df2)

    latest1 = df1.iloc[-1]
    latest2 = df2.iloc[-1]

    prompt = f"""
    Bandingkan dua saham berikut secara teknikal:

    SAHAM 1: {symbol1}
    Data terkini ({latest1['Date'].strftime('%Y-%m-%d')}):
    - Harga: {latest1['Close']:.2f}
    - RSI: {latest1['RSI']:.2f}
    - MACD: {latest1['MACD']:.2f}, Signal: {latest1['MACD_signal']:.2f}
    - EMA20: {latest1['EMA20']:.2f}, EMA50: {latest1['EMA50']:.2f}
    - Volume: {latest1['Volume']:.0f} (rata-rata 20 hari: {latest1['Volume_MA20']:.0f})

    SAHAM 2: {symbol2}
    Data terkini ({latest2['Date'].strftime('%Y-%m-%d')}):
    - Harga: {latest2['Close']:.2f}
    - RSI: {latest2['RSI']:.2f}
    - MACD: {latest2['MACD']:.2f}, Signal: {latest2['MACD_signal']:.2f}
    - EMA20: {latest2['EMA20']:.2f}, EMA50: {latest2['EMA50']:.2f}
    - Volume: {latest2['Volume']:.0f} (rata-rata 20 hari: {latest2['Volume_MA20']:.0f})

    Berdasarkan data di atas:
    1. Bandingkan tren, momentum, dan kekuatan kedua saham.
    2. Mana yang lebih oversold atau overbought?
    3. Mana yang lebih menarik untuk swing trading minggu depan? Jelaskan alasannya.
    4. Berikan rekomendasi: beli salah satu, tahan, atau tunggu.

    Jawab dalam Bahasa Indonesia, terstruktur dan jelas.
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800
            )
            await send_long_message(update, response.choices[0].message.content)
            break
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                await update.message.reply_text("⚠️ Server AI sibuk, mencoba lagi...")
                await asyncio.sleep(5)
            else:
                await update.message.reply_text(f"Error: {e}")
                break

# ======================================================================
# HANDLER /calendar
# ======================================================================
async def calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = get_economic_calendar()
    text = format_calendar(events)
    await update.message.reply_text(text)

# ======================================================================
# HANDLER /risk
# ======================================================================
async def risk_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = get_state_info()
    cooldown_text = info['cooldown_until'] if info['cooldown_until'] else 'Tidak ada'
    text = (
        "📊 *Status Risiko*\n"
        f"• Loss hari ini: {info['daily_loss']:.2f}% / {info['daily_loss_cap']}%\n"
        f"• Loss bulan ini: {info['monthly_loss']:.2f}% / 15%\n"
        f"• Trade hari ini: {info['trade_count']}\n"
        f"• Cooldown: {cooldown_text}\n"
        f"• Crash mode: {'Aktif' if info['crash_mode'] else 'Tidak'}"
    )
    await update.message.reply_text(text)

async def set_risk_cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text(
            "Format: /set_cap <persen>\n"
            "Contoh: /set_cap 3.5\n"
            "Mengubah batas loss harian."
        )
        return
    try:
        new_cap = float(context.args[0])
        set_daily_loss_cap(new_cap)
        await update.message.reply_text(f"✅ Daily loss cap diubah menjadi {new_cap}%")
    except ValueError:
        await update.message.reply_text("❌ Masukkan angka yang valid.")

# ======================================================================
# HANDLER /walkforward
# ======================================================================
async def walkforward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text(
            "Format: /walkforward <kode>\n"
            "Contoh: /walkforward BBCA\n"
            "Melakukan walk-forward analysis untuk saham tersebut."
        )
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'

    await update.message.reply_text(f"⏳ Menjalankan walk-forward untuk {symbol}... (mungkin butuh 1-2 menit)")

    param_grid = []
    for rsi_os in [25, 30, 35]:
        for rsi_ob in [65, 70, 75]:
            for adx_th in [20, 25, 30]:
                param_grid.append({
                    'rsi_oversold': rsi_os,
                    'rsi_overbought': rsi_ob,
                    'adx_threshold': adx_th
                })

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        try:
            results = await loop.run_in_executor(pool, walk_forward, symbol, param_grid, 1.5, 0.5)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
            return

    if not results:
        await update.message.reply_text("❌ Tidak ada jendela walk-forward yang dapat dibuat.")
        return

    lines = [f"📊 *Walk-Forward Analysis {symbol}*\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"*Jendela {i}*")
        lines.append(f"Train: {r['train_start'].strftime('%d/%m/%Y')} - {r['train_end'].strftime('%d/%m/%Y')}")
        lines.append(f"Test : {r['test_start'].strftime('%d/%m/%Y')} - {r['test_end'].strftime('%d/%m/%Y')}")
        lines.append(f"Parameter terbaik:")
        lines.append(f"  RSI os: {r['best_params']['rsi_oversold']}, ob: {r['best_params']['rsi_overbought']}, ADX: {r['best_params']['adx_threshold']}")
        lines.append(f"Hasil Test:")
        lines.append(f"  Return: {r['test_metrics']['total_return']:.2f}%")
        lines.append(f"  Win Rate: {r['test_metrics']['win_rate']:.1f}%")
        lines.append(f"  Profit Factor: {r['test_metrics']['profit_factor']:.2f}")
        lines.append(f"  Trades: {r['test_metrics']['num_trades']}\n")

    await send_long_message(update, '\n'.join(lines))

# ======================================================================
# HANDLER /robust
# ======================================================================
async def robust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text(
            "Format: /robust <kode>\n"
            "Contoh: /robust BBCA\n"
            "Melakukan robustness test pada parameter default."
        )
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'

    await update.message.reply_text(f"⏳ Menjalankan robustness test untuk {symbol}...")

    base_params = {'rsi_oversold': 30, 'rsi_overbought': 70, 'adx_threshold': 25}
    variasi = {'rsi_oversold': [-5, 0, 5], 'rsi_overbought': [-5, 0, 5], 'adx_threshold': [-5, 0, 5]}

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        try:
            results = await loop.run_in_executor(pool, robustness_test, symbol, base_params, variasi)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
            return

    if not results:
        await update.message.reply_text("❌ Tidak ada hasil robustness test.")
        return

    returns = [r['metrics']['total_return'] for r in results]
    win_rates = [r['metrics']['win_rate'] for r in results]
    profit_factors = [r['metrics']['profit_factor'] for r in results]

    lines = [
        f"📊 *Robustness Test {symbol}*\n",
        f"Parameter dasar: RSI os=30, ob=70, ADX=25",
        f"Jumlah variasi: {len(results)}\n",
        f"*Statistik Return*",
        f"  Rata-rata: {np.mean(returns):.2f}%",
        f"  Std Dev: {np.std(returns):.2f}%",
        f"  Min: {np.min(returns):.2f}%",
        f"  Max: {np.max(returns):.2f}%",
        f"*Statistik Win Rate*",
        f"  Rata-rata: {np.mean(win_rates):.1f}%",
        f"  Std Dev: {np.std(win_rates):.1f}%",
        f"*Statistik Profit Factor*",
        f"  Rata-rata: {np.mean(profit_factors):.2f}",
        f"  Std Dev: {np.std(profit_factors):.2f}",
    ]

    await send_long_message(update, '\n'.join(lines))

# ======================================================================
# HANDLER /journal
# ======================================================================
async def journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) > 0:
        try:
            days = int(context.args[0])
        except:
            days = 7
    else:
        days = 7

    summary = get_journal_summary(days)
    text = f"📊 *Jurnal Trading - {days} Hari Terakhir*\n"
    text += f"Total Trades: {summary['total_trades']}\n"
    text += f"Total PnL: Rp {summary['total_pnl']:,.0f}\n"
    text += f"Rata-rata PnL %: {summary['avg_pnl_pct']:.2f}%\n"
    text += f"Win Rate: {summary['win_rate']:.1f}%\n\n"

    if summary['open_positions']:
        text += "*Posisi Terbuka:*\n"
        for pos in summary['open_positions']:
            symbol, entry_date, entry_price, qty = pos
            text += f"• {symbol}: {qty} lot @ {entry_price:,.0f} (entry {entry_date})\n"
    else:
        text += "Tidak ada posisi terbuka.\n"

    recent = get_recent_trades(5)
    if recent:
        text += "\n*5 Trade Terbaru:*\n"
        for t in recent:
            symbol, entry_date, entry_price, exit_date, exit_price, pnl_pct, status = t
            if status == 'closed':
                text += f"• {symbol}: {entry_date} → {exit_date} {pnl_pct:+.2f}%\n"
            else:
                text += f"• {symbol}: {entry_date} (open) @ {entry_price:,.0f}\n"

    await send_long_message(update, text)

# ======================================================================
# HANDLER /paper
# ======================================================================
async def paper_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    status = "AKTIF" if config['paper_mode'] else "TIDAK AKTIF"
    balance = config['paper_balance']
    initial = config['initial_balance']
    pnl = balance - initial
    pnl_pct = (pnl / initial) * 100
    text = (
        f"📄 *Paper Trading*\n"
        f"Status: {'🟢 ' + status if config['paper_mode'] else '🔴 ' + status}\n"
        f"Saldo: Rp {balance:,.0f}\n"
        f"Return: {pnl:+,.0f} ({pnl_pct:+.2f}%)\n"
        f"Posisi Terbuka: {len(config['open_positions'])}"
    )
    await update.message.reply_text(text)

async def paper_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_mode = toggle_paper_mode()
    mode_text = "AKTIF" if new_mode else "TIDAK AKTIF"
    await update.message.reply_text(f"✅ Mode paper sekarang {mode_text}.")

async def paper_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_paper_balance()
    await update.message.reply_text("✅ Saldo paper direset ke Rp 100.000.000.")

# ======================================================================
# HANDLER /optimize
# ======================================================================
async def optimize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /optimize <kode>")
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'
    await update.message.reply_text(f"⏳ Menjalankan optimasi untuk {symbol}... (mungkin butuh 1-2 menit)")

    param_grid = []
    for rsi_os in [30, 35, 40]:
        for rsi_ob in [60, 65, 70]:
            for adx_th in [20, 25, 30]:
                param_grid.append({
                    'rsi_oversold': rsi_os,
                    'rsi_overbought': rsi_ob,
                    'adx_threshold': adx_th
                })

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        try:
            results = await loop.run_in_executor(pool, walk_forward, symbol, param_grid, 1.5, 0.5)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
            return

    if not results:
        await update.message.reply_text("❌ Tidak ada hasil walk-forward.")
        return

    best_params = results[-1]['best_params']
    from scripts.strategy_selector import load_optimal_params, save_optimal_params
    optimal = load_optimal_params()
    optimal['trend_swing'] = best_params
    save_optimal_params(optimal)

    await update.message.reply_text(
        f"✅ Parameter terbaik untuk {symbol} telah disimpan: "
        f"RSI os={best_params['rsi_oversold']}, ob={best_params['rsi_overbought']}, ADX={best_params['adx_threshold']}"
    )


async def econ_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from scripts.economic_risk import get_current_risk_level
    risk = get_current_risk_level()
    emoji = "🟢" if risk['risk_level'] == 'LOW' else "🟡" if risk['risk_level'] == 'MEDIUM' else "🔴"
    msg = f"{emoji} *Risiko Ekonomi: {risk['risk_level']}*\n"
    msg += risk['message'] + "\n"
    if 'high_impact_count' in risk:
        msg += f"High impact events: {risk['high_impact_count']}"
    await update.message.reply_text(msg)

# scripts/telegram_bot.py (tambahkan handler baru)

async def econid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan data ekonomi Indonesia terkini."""
    import sqlite3
    import pandas as pd
    
    conn = sqlite3.connect('data/saham.db')
    df = pd.read_sql("SELECT * FROM economic_indonesia_data ORDER BY date DESC, indicator", conn)
    conn.close()
    
    if df.empty:
        await update.message.reply_text("❌ Data ekonomi Indonesia belum tersedia.")
        return
    
    # Ambil data terbaru untuk setiap indikator
    latest = df.sort_values('date', ascending=False).groupby('indicator').first().reset_index()
    
    msg = "📊 *Data Ekonomi Indonesia Terkini*\n\n"
    for _, row in latest.iterrows():
        msg += f"• *{row['description']}*\n"
        msg += f"  Tahun: {row['date']} | Nilai: {row['value']:,.2f}\n"
        msg += f"  Update: {row['updated_at'][:10]}\n\n"
    
    await send_long_message(update, msg)

# ======================================================================
# HANDLER /clusters - Menampilkan klaster saham
# ======================================================================
async def clusters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan klaster saham dari berita."""
    tracker = get_tracker()
    clusters = tracker.get_latest_clusters()
    
    if not clusters:
        await update.message.reply_text("❌ Belum ada data klaster. Jalankan update dulu.")
        return
    
    msg = "📊 *Klaster Saham dari Berita*\n\n"
    for c in clusters:
        msg += f"• *{c['name']}* ({len(c['symbols'])} saham)\n"
        msg += f"  {', '.join(c['symbols'][:5])}"
        if len(c['symbols']) > 5:
            msg += f" dan {len(c['symbols'])-5} lainnya"
        msg += f"\n  Deteksi: {c['detected_at'][:10]}\n\n"
    
    await send_long_message(update, msg)

# ======================================================================
# HANDLER /clustersent - Menampilkan sentimen klaster
# ======================================================================
async def cluster_sentiment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan sentimen klaster saham."""
    tracker = get_tracker()
    recommendations = tracker.get_cluster_recommendations()
    
    msg = "📈 *Rekomendasi Berdasarkan Sentimen Klaster*\n\n"
    
    msg += "*🔴 Kandidat Beli (Sentimen Positif)*\n"
    for rec in recommendations['buy_candidates'][:5]:
        msg += f"• {rec['cluster']}: {rec['symbols'][:50]}... (score: {rec['score']:.2f})\n"
    
    msg += "\n*🔵 Kandidat Jual (Sentimen Negatif)*\n"
    for rec in recommendations['sell_candidates'][:5]:
        msg += f"• {rec['cluster']}: {rec['symbols'][:50]}... (score: {rec['score']:.2f})\n"
    
    await send_long_message(update, msg)

# ======================================================================
# HANDLER /cooccur <kode> - Menampilkan saham yang sering muncul bersama
# ======================================================================
async def cooccur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan saham yang sering muncul bersama dengan suatu kode."""
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /cooccur <kode>")
        return
    
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'
    
    tracker = get_tracker()
    related = tracker.get_cooccurrence_for_symbol(symbol)
    
    if not related:
        await update.message.reply_text(f"ℹ️ Tidak ada data co-occurrence untuk {symbol}")
        return
    
    msg = f"🔗 *Saham yang Sering Muncul Bersama {symbol}*\n\n"
    for r in related:
        msg += f"• {r['symbol']} (weight: {r['weight']})\n"
    
    await update.message.reply_text(msg)

# ======================================================================
# HANDLER /import_status
# ======================================================================
async def import_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan status data terakhir untuk setiap saham."""
    conn = sqlite3.connect('data/saham.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Symbol, MAX(Date) FROM saham
        GROUP BY Symbol
        ORDER BY Symbol
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await update.message.reply_text("Belum ada data saham.")
        return
    
    msg = "📅 *Status Data Saham*\n\n"
    for symbol, last_date in rows:
        msg += f"• {symbol}: {last_date}\n"
    
    await send_long_message(update, msg)

# ======================================================================
# HANDLER /retrain
# ======================================================================
async def retrain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memicu training ulang model ML untuk saham tertentu."""
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /retrain <kode>\nContoh: /retrain BBCA")
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'
    
    await update.message.reply_text(f"⏳ Melatih model untuk {symbol}... (mungkin butuh beberapa menit)")
    
    from scripts.ml_train_advanced import train_advanced_model
    try:
        result = train_advanced_model(symbol, target_days=5, tune=True, n_iter=20)
        msg = f"✅ Training selesai untuk {symbol}\n"
        msg += f"Best CV accuracy: {result['best_cv_score']:.4f}\n"
        msg += f"Test accuracy: {result['accuracy']:.4f}\n"
        msg += f"Best params: {result['best_params']}"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal: {e}")

# ======================================================================
# HANDLER /clusters_update
# ======================================================================
async def clusters_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memperbarui klaster berita secara manual."""
    await update.message.reply_text("⏳ Memperbarui klaster berita...")
    from scripts.update_clusters import update_all_clusters
    try:
        success = update_all_clusters()
        if success:
            await update.message.reply_text("✅ Klaster berita berhasil diperbarui.")
        else:
            await update.message.reply_text("⚠️ Tidak ada klaster baru atau terjadi error.")
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal: {e}")

# ======================================================================
# HANDLER /export
# ======================================================================
async def export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mengekspor data saham ke CSV."""
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /export <kode>\nContoh: /export BBCA")
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'
    
    from scripts.export_data import export_saham_to_csv
    csv_bytes = export_saham_to_csv(symbol)
    if csv_bytes is None:
        await update.message.reply_text(f"❌ Data untuk {symbol} tidak ditemukan.")
        return
    
    # Kirim sebagai file
    import io
    await update.message.reply_document(
        document=io.BytesIO(csv_bytes),
        filename=f"{symbol}.csv",
        caption=f"Data historis {symbol}"
    )

# ======================================================================
# HANDLER /mlreport
# ======================================================================
async def mlreport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan laporan performa model ML."""
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /mlreport <kode>\nContoh: /mlreport BBCA")
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'
    
    from scripts.ml_predictor_advanced import get_ml_report
    report = get_ml_report(symbol)
    if report is None:
        await update.message.reply_text(f"ℹ️ Tidak ada laporan untuk {symbol}. Latih model dulu dengan /retrain.")
        return
    
    msg = f"📊 *Laporan ML {symbol}*\n"
    msg += f"Best CV accuracy: {report.get('best_cv_score', 0):.4f}\n"
    msg += f"Test accuracy: {report.get('accuracy', 0):.4f}\n"
    msg += f"Best params: {report.get('best_params', {})}"
    await update.message.reply_text(msg)

async def regime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan regime pasar untuk saham tertentu."""
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /regime <kode>\nContoh: /regime BBCA")
        return
    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'
    
    from scripts.analisis_adaptif import ambil_data_dari_db, tambah_indikator
    from scripts.regime_classifier import get_regime_classifier
    
    df = ambil_data_dari_db(symbol, hari=100)
    if df is None or len(df) < 50:
        await update.message.reply_text(f"Data untuk {symbol} tidak cukup.")
        return
    
    df = tambah_indikator(df)
    classifier = get_regime_classifier()
    regime = classifier.predict_regime(df)
    description = classifier.get_regime_description(regime)
    
    msg = f"📊 *Regime Pasar {symbol}*\n"
    msg += f"Regime: {regime}\n"
    msg += f"Keterangan: {description}"
    await update.message.reply_text(msg)

# Di telegram_bot.py, tambahkan handler baru

async def agent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan sinyal multi-agent, dengan auto-training jika model belum ada."""
    logger.info(f"agent_command dipanggil dengan args: {context.args}")
    try:
        if len(context.args) < 1:
            await update.message.reply_text("❌ Format: /agent <kode>\nContoh: /agent BBCA")
            return

        raw = context.args[0].upper()
        symbol = raw if raw.endswith('.JK') else raw + '.JK'
        logger.info(f"Memproses agent untuk {symbol}")

        # Impor modul yang diperlukan
        from scripts.analisis_adaptif import ambil_data_dari_db, tambah_indikator
        from scripts.regime_classifier import get_regime_classifier
        from scripts.multi_agent_selector import get_multi_agent
        from scripts.ml_predictor_advanced import get_predictor
        from scripts.ensemble_predictor import EnsemblePredictor
        from scripts.agent_cache import get_agent_cache
        from scripts.training_queue import get_training_queue

        # Ambil data historis (100 hari cukup untuk analisis)
        df = ambil_data_dari_db(symbol, hari=100)
        if df is None or len(df) < 50:
            await update.message.reply_text(f"❌ Data untuk {symbol} tidak cukup (minimal 50 hari).")
            return

        df = tambah_indikator(df)
        logger.info(f"Data {symbol} berhasil diambil, {len(df)} baris")

        # === Cek cache ===
        cache = get_agent_cache()
        cached_result = cache.get(symbol)
        if cached_result:
            logger.info(f"Menggunakan cached result untuk {symbol}")
            regime = cached_result['regime']
            agent_signal = cached_result['agent_signal']
            agent_confidence = cached_result['agent_confidence']
            details = cached_result['details']
        else:
            # Deteksi regime pasar
            classifier = get_regime_classifier()
            if not classifier.is_trained:
                logger.warning("Regime classifier belum terlatih, gunakan fallback")
                regime = "unknown"
            else:
                regime = classifier.predict_regime(df)
            logger.info(f"Regime terdeteksi: {regime}")

            # Dapatkan instance multi-agent
            multi_agent = get_multi_agent()
            multi_agent.update_regime(regime)

            # Dapatkan sinyal dari semua agent
            agent_signal, agent_confidence, details = multi_agent.get_consensus_signal(symbol, df)

            # Simpan ke cache
            cache.set(symbol, {
                'regime': regime,
                'agent_signal': agent_signal,
                'agent_confidence': agent_confidence,
                'details': details
            })

        # === Cek ketersediaan model XGBoost dan ensemble ===
        predictor = get_predictor(symbol)
        model_available = predictor is not None

        ensemble_available = False
        try:
            ensemble = EnsemblePredictor(symbol)
            ensemble_available = True
        except Exception as e:
            logger.debug(f"Ensemble untuk {symbol} tidak ditemukan: {e}")
            ensemble_available = False

        # Cek ketersediaan LSTM
        from scripts.lstm_predictor import load_lstm
        lstm_available = False
        try:
            model, _, _ = load_lstm(symbol)
            lstm_available = model is not None
        except Exception as e:
            logger.debug(f"LSTM untuk {symbol} tidak ditemukan: {e}")
            lstm_available = False

        # === Tambahkan task ke antrean training jika belum ada ===
        queue = get_training_queue()

        if not ensemble_available:
            success = queue.add_task(symbol, 'ensemble', update.effective_chat.id, context)
            if success:
                await update.message.reply_text(
                    f"⏳ Model ensemble untuk {symbol} belum tersedia.\n"
                    f"Task telah ditambahkan ke antrean training (posisi: {queue.get_queue_size()}).\n"
                    f"Anda akan mendapat notifikasi saat model siap."
                )
            else:
                await update.message.reply_text(
                    f"ℹ️ Model ensemble untuk {symbol} sedang dalam antrean. Harap tunggu."
                )

        if not lstm_available:
            success = queue.add_task(symbol, 'lstm', update.effective_chat.id, context)
            if success:
                await update.message.reply_text(
                    f"⏳ Model LSTM untuk {symbol} belum tersedia.\n"
                    f"Task telah ditambahkan ke antrean training (posisi: {queue.get_queue_size()}).\n"
                    f"Anda akan mendapat notifikasi saat model siap."
                )
            else:
                await update.message.reply_text(
                    f"ℹ️ Model LSTM untuk {symbol} sedang dalam antrean. Harap tunggu."
                )

        # === Bangun pesan respons ===
        msg = f"🤖 *Multi-Agent Analysis {symbol}*\n"
        msg += f"Regime: {regime}\n\n"

        for d in details:
            if d.get('prob_up', 0) > d.get('prob_down', 0):
                direction = "BUY"
            else:
                direction = "SELL"
            # Jika agent Momentum dan tidak ada model sama sekali, tampilkan PENDING
            if d['name'] == 'Momentum' and not (model_available or ensemble_available or lstm_available):
                direction = "PENDING"
                reason = "Model sedang dilatih, coba lagi nanti"
            else:
                reason = d['reason'][:50]
            msg += f"• {d['name']}: {direction} (conf {d['confidence']:.1f}%, reason: {reason})\n"

        if agent_signal == 1:
            consensus_dir = "BUY"
        elif agent_signal == -1:
            consensus_dir = "SELL"
        else:
            consensus_dir = "NETRAL"
        msg += f"\n*Konsensus:* {consensus_dir} (conf {agent_confidence:.1f}%)"

        await update.message.reply_text(msg)
        logger.info(f"Respon agent untuk {symbol} berhasil dikirim")

    except Exception as e:
        logger.exception(f"Error di agent_command untuk {symbol if 'symbol' in locals() else 'unknown'}: {e}")
        await update.message.reply_text(f"❌ Terjadi error internal: {str(e)}")

# ======================================================================
# HANDLER /train_all - Melatih model ML untuk semua saham di watchlist
# ======================================================================
async def train_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Memulai training model ML untuk semua saham di watchlist... (mungkin butuh waktu lama)")
    from scripts.ml_train_advanced import train_all_advanced
    import asyncio
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, train_all_advanced, True, True)
    await update.message.reply_text(f"✅ Training selesai. Model diperbarui untuk {len(result)} saham.")

# ======================================================================
# HANDLER /update_econ - Update data ekonomi FRED
# ======================================================================
async def update_econ(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Memperbarui data ekonomi FRED...")
    from scripts.economic_fetcher import get_fetcher
    fetcher = get_fetcher()
    success = fetcher.update_economic_data()
    if success:
        await update.message.reply_text("✅ Data ekonomi FRED berhasil diperbarui.")
    else:
        await update.message.reply_text("❌ Gagal memperbarui data ekonomi FRED.")

# ======================================================================
# HANDLER /update_econid - Update data ekonomi Indonesia
# ======================================================================
async def update_econid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Memperbarui data ekonomi Indonesia (World Bank + libur nasional)...")
    from scripts.economic_indonesia import get_econ_fetcher, get_holiday_fetcher
    econ = get_econ_fetcher()
    econ_success = econ.update_economic_data()
    holiday = get_holiday_fetcher()
    holiday_success = holiday.update_holidays()
    if econ_success or holiday_success:
        msg = "✅ Data ekonomi Indonesia berhasil diperbarui.\n"
        if econ_success:
            msg += " - Ekonomi World Bank: sukses\n"
        else:
            msg += " - Ekonomi World Bank: gagal\n"
        if holiday_success:
            msg += " - Libur nasional: sukses"
        else:
            msg += " - Libur nasional: gagal"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ Semua update gagal.")

# ======================================================================
# HANDLER /train_regime - Melatih ulang model GMM regime classifier
# ======================================================================
async def train_regime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Melatih ulang model GMM regime classifier...")
    from scripts.train_regime import train_regime_classifier
    from scripts.data_utils import get_all_symbols
    import asyncio
    loop = asyncio.get_event_loop()
    symbols = get_all_symbols()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, train_regime_classifier, symbols)
    if result:
        await update.message.reply_text("✅ Model regime berhasil dilatih.")
    else:
        await update.message.reply_text("❌ Gagal melatih model regime.")

# ======================================================================
# HANDLER /mlstatus - Menampilkan status model ML
# ======================================================================
async def mlstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import os, glob, json
    from scripts.ml_predictor_advanced import REPORT_DIR
    files = glob.glob(os.path.join(REPORT_DIR, "*_metrics.json"))
    if not files:
        await update.message.reply_text("ℹ️ Belum ada model yang dilatih.")
        return
    msg = "📊 *Status Model ML*\n\n"
    for f in files[-10:]:  # tampilkan 10 terakhir
        with open(f, 'r') as fp:
            data = json.load(fp)
        symbol = os.path.basename(f).replace("_metrics.json", "")
        cv_acc = data.get('best_cv_score', 0)
        test_acc = data.get('accuracy', 0)
        updated = os.path.getmtime(f)
        from datetime import datetime
        updated_str = datetime.fromtimestamp(updated).strftime('%Y-%m-%d %H:%M')
        msg += f"• {symbol}: CV={cv_acc:.3f}, Test={test_acc:.3f} ({updated_str})\n"
    await send_long_message(update, msg)

# ======================================================================
# (Opsional) HANDLER /errors - Menampilkan 10 baris error terbaru dari log
# ======================================================================
async def errors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan 10 baris error terbaru dari log."""
    log_file = 'trading_bot.log'
    if not os.path.exists(log_file):
        await update.message.reply_text("ℹ️ File log tidak ditemukan.")
        return
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Jika gagal dengan utf-8, coba dengan encoding default (cp1252) dan abaikan error
        with open(log_file, 'r', encoding='cp1252', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal membaca log: {e}")
        return
    
    error_lines = [line.strip() for line in lines if 'ERROR' in line]
    if not error_lines:
        await update.message.reply_text("✅ Tidak ada error dalam log.")
        return
    
    last_errors = error_lines[-10:]
    msg = "⚠️ *10 Error Terbaru*\n\n"
    for e in last_errors:
        msg += e + "\n"
    
    # Kirim pesan, potong jika terlalu panjang
    if len(msg) > 4096:
        msg = msg[:4000] + "\n\n... (terpotong)"
    
    await update.message.reply_text(msg)

async def rlstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from scripts.rl_agent import get_rl_orchestrator
    rl = get_rl_orchestrator()
    msg = "📊 *RL Orchestrator Q-Table*\n\n"
    regime_names = ['Trending Bull', 'Trending Bear', 'Sideways', 'High Vol']
    agent_names = ['XGBoost', 'Mean Rev', 'Breakout', 'Gorengan', 'Voting']
    
    for i, regime in enumerate(regime_names):
        msg += f"*{regime}*\n"
        for j, agent in enumerate(agent_names):
            msg += f"  • {agent}: {rl.q_table[i][j]:.2f}\n"
        msg += "\n"
    
    await update.message.reply_text(msg)

async def dqnstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from scripts.multi_agent_selector import get_multi_agent
    ma = get_multi_agent()
    agent = ma.dqn_agent
    msg = f"🤖 *DQN Agent Status*\n"
    msg += f"State size: {agent.state_size}\n"
    msg += f"Action size: {agent.action_size}\n"
    msg += f"Epsilon: {agent.epsilon:.3f}\n"
    msg += f"Memory size: {len(agent.memory)}\n"
    msg += f"Train step: {agent.train_step}\n"
    await update.message.reply_text(msg)

async def sectors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from scripts.sector_rotation import get_sector_analyzer
    analyzer = get_sector_analyzer()
    strong = analyzer.get_strongest_sectors(top_n=5)
    if not strong:
        await update.message.reply_text("Belum ada data sektor.")
        return
    msg = "📊 *Sektor Terkuat*\n\n"
    for s in strong:
        msg += f"• {s['cluster']}: Sharpe {s['sharpe']:.2f}, Return {s['return']*100:.1f}%\n"
    await update.message.reply_text(msg)

async def strategies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import glob, json, os
    files = glob.glob('best_strategies_*.json')
    if not files:
        await update.message.reply_text("Belum ada strategi tersimpan.")
        return
    latest = max(files, key=os.path.getctime)
    with open(latest, 'r') as f:
        strategies = json.load(f)
    msg = "📊 *Strategi Terbaik*\n\n"
    for i, strat in enumerate(strategies[:5]):  # tampilkan 5 teratas
        # Pastikan field yang benar
        name = strat.get('name') or strat.get('strategy_name') or f"Strategi {i+1}"
        total_return = strat.get('total_return', 0)
        win_rate = strat.get('win_rate', 0)
        trades = strat.get('num_trades', 0)
        msg += f"*{i+1}. {name}*\n"
        msg += f"   Return: {total_return:.2f}% | Win Rate: {win_rate:.1f}%\n"
        msg += f"   Trades: {trades}\n\n"
    await update.message.reply_text(msg)

async def weights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from scripts.multi_agent_selector import get_multi_agent
    multi_agent = get_multi_agent()
    msg = "⚖️ *Bobot Agent Saat Ini*\n\n"
    for name, _, weight in multi_agent.analysts:
        msg += f"• {name}: {weight:.3f}\n"
    await update.message.reply_text(msg)

async def update_fundamental_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Memperbarui data fundamental untuk SEMUA saham di database.
    Penggunaan: /update_fundamental_all
    """
    logger.info("update_fundamental_all_command dipanggil")
    
    # Kirim pesan segera bahwa proses dimulai
    await update.message.reply_text("⏳ Memulai update fundamental untuk SEMUA saham. Proses ini akan memakan waktu lama (beberapa menit hingga jam tergantung jumlah saham). Anda akan mendapat notifikasi saat selesai.")
    
    # Jalankan update di thread terpisah agar tidak memblokir bot
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        try:
            success, total = await loop.run_in_executor(
                pool,
                update_all_fundamental,
                False,  # use_watchlist = False
                1.5     # delay antar request
            )
            # Kirim notifikasi hasil
            if success > 0:
                await update.message.reply_text(f"✅ Update fundamental selesai! {success}/{total} saham berhasil diperbarui.")
            else:
                await update.message.reply_text(f"⚠️ Tidak ada data yang berhasil diperbarui. Periksa log untuk detail.")
        except Exception as e:
            logger.exception(f"Error saat update fundamental semua saham: {e}")
            await update.message.reply_text(f"❌ Terjadi error: {str(e)}")

async def update_historical_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memicu update data historical untuk semua saham."""
    logger.info("update_historical_command dipanggil")
    
    await update.message.reply_text("⏳ Memulai update data historical untuk SEMUA saham. Proses ini mungkin memakan waktu 5-10 menit...")
    
    # Jalankan di thread terpisah
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        try:
            symbols = get_all_symbols()
            success, total = await loop.run_in_executor(
                pool,
                update_all_historical,
                symbols,
                365,   # days_back
                1.0    # delay
            )
            await update.message.reply_text(f"✅ Update selesai! {success}/{total} saham berhasil diperbarui.")
        except Exception as e:
            logger.exception(f"Error update historical: {e}")
            await update.message.reply_text(f"❌ Terjadi error: {str(e)}")

async def lstm_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from scripts.lstm_predictor import _training_in_progress, MODEL_DIR
    import os
    
    models = [f.replace('_lstm.pth', '') for f in os.listdir(MODEL_DIR) if f.endswith('_lstm.pth')]
    training = list(_training_in_progress)
    
    msg = f"📊 *Status Model LSTM*\n\n"
    msg += f"Model tersedia: {len(models)} saham\n"
    msg += f"Sedang training: {', '.join(training) if training else 'Tidak ada'}\n"
    msg += f"Proses tuning BBCA: {'Sedang berjalan' if 'BBCA.JK' in training else 'Selesai'}"
    
    await update.message.reply_text(msg)

async def top5_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan 5 saham rekomendasi terbaik dengan diversifikasi."""
    await update.message.reply_text(
        "🔍 Mencari rekomendasi 5 saham terbaik...\n"
        "Proses ini bisa memakan waktu 2-3 menit untuk 600+ saham."
    )
    
    from scripts.rekomendasi import select_top_stocks, format_recommendations
    
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        results = await loop.run_in_executor(pool, select_top_stocks, 5, 5, True)
    
    if results:
        text = format_recommendations(results)
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("❌ Tidak ada hasil rekomendasi.")

async def evaluate_agents_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan evaluasi performa agen."""
    from scripts.evaluate_agents import evaluate_agent_performance, print_evaluation_results
    
    results = evaluate_agent_performance(days_back=30)
    if results:
        text = print_evaluation_results(results)
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("Tidak ada data evaluasi untuk 30 hari terakhir.")

async def cek_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Gunakan: /cek_data <kode>")
        return
    symbol = context.args[0].upper() + '.JK'
    from scripts.data_utils import ambil_data_dari_db
    df = ambil_data_dari_db(symbol, hari=10)
    if df is not None:
        msg = f"Data terbaru {symbol}:\n"
        for _, row in df.iterrows():
            msg += f"{row['Date'].strftime('%Y-%m-%d')}: {row['Close']}\n"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text(f"Data untuk {symbol} tidak ditemukan.")

async def datacheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memeriksa jumlah baris data historis untuk suatu saham."""
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /datacheck <kode>\nContoh: /datacheck BBCA")
        return

    raw = context.args[0].upper()
    symbol = raw if raw.endswith('.JK') else raw + '.JK'

    import sqlite3
    conn = sqlite3.connect('data/saham.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM saham WHERE Symbol=?", (symbol,))
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        msg = f"📊 *{symbol}*: Tidak ada data historis."
    else:
        cukup = "✅ CUKUP" if count >= 500 else "❌ KURANG"
        msg = f"📊 *{symbol}*: {count} baris data.\nStatus untuk training XGBoost: {cukup} (minimal 500 baris)."
    
    await update.message.reply_text(msg)

async def jelas_multi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Menampilkan analisis cepat untuk beberapa saham sekaligus.
    Format: /jelas_multi <kode1> <kode2> ...
    Contoh: /jelas_multi BBCA BBRI TLKM
    """
    if len(context.args) < 1:
        await update.message.reply_text("❌ Format: /jelas_multi <kode1> <kode2> ...\nContoh: /jelas_multi BBCA BBRI TLKM")
        return

    symbols = []
    for arg in context.args:
        raw = arg.upper()
        symbol = raw if raw.endswith('.JK') else raw + '.JK'
        symbols.append(symbol)

    await update.message.reply_text(f"⏳ Menganalisis {len(symbols)} saham, mohon tunggu...")

    from scripts.analisis_adaptif import ambil_data_dari_db, tambah_indikator
    from scripts.formatters import format_rupiah, format_volume
    from scripts.fundamental import enrich_with_fundamental, fundamental_score

    for symbol in symbols:
        try:
            df = ambil_data_dari_db(symbol, hari=100)
            if df is None or len(df) < 10:
                await update.message.reply_text(f"❌ {symbol}: Data tidak cukup.")
                continue

            df = tambah_indikator(df)
            latest = df.iloc[-1]
            recent_low = df['Low'].tail(20).min()
            recent_high = df['High'].tail(20).max()

            if latest['RSI'] < 30:
                kondisi = "oversold"
            elif latest['RSI'] > 70:
                kondisi = "overbought"
            else:
                kondisi = "netral"

            msg = f"📈 *Analisis Cepat {symbol}*\n"
            msg += f"🗓️ {latest['Date'].strftime('%d %b %Y')}\n"
            msg += f"💵 Harga: {format_rupiah(latest['Close'])}\n"
            msg += f"📊 RSI: {latest['RSI']:.1f} ({kondisi})\n"
            msg += f"📉 EMA20: {format_rupiah(latest['EMA20'])} | EMA50: {format_rupiah(latest['EMA50'])}\n"
            msg += f"📈 ADX: {latest['ADX']:.1f} | Volume: {format_volume(latest['Volume'])}\n"
            msg += f"🔝 Resistance: {format_rupiah(recent_high)} | 🔻 Support: {format_rupiah(recent_low)}\n"

            fundamental = enrich_with_fundamental(symbol)
            if fundamental:
                fund_score, fund_reason = fundamental_score(fundamental)
                msg += f"📊 Skor Fundamental: {fund_score}\n"
            await update.message.reply_text(msg)
        except Exception as e:
            logger.exception(f"Error di jelas_multi untuk {symbol}: {e}")
            await update.message.reply_text(f"❌ {symbol}: Error saat analisis.")

async def tf_multi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Analisis multi-timeframe untuk beberapa saham.
    Format: /tf_multi <arah> <kode1> <kode2> ...
    Arah opsional: buy atau sell (default buy)
    Contoh: /tf_multi buy BBCA BBRI TLKM
    """
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format: /tf_multi <arah> <kode1> <kode2> ...\n"
            "Arah: buy atau sell (default buy)\n"
            "Contoh: /tf_multi buy BBCA BBRI TLKM"
        )
        return

    # Tentukan arah
    first = context.args[0].lower()
    if first in ['buy', 'sell']:
        target_direction = first
        symbols_raw = context.args[1:]
    else:
        target_direction = 'buy'
        symbols_raw = context.args

    if not symbols_raw:
        await update.message.reply_text("❌ Tidak ada kode saham yang diberikan.")
        return

    symbols = []
    for arg in symbols_raw:
        raw = arg.upper()
        symbol = raw if raw.endswith('.JK') else raw + '.JK'
        symbols.append(symbol)

    await update.message.reply_text(f"⏳ Menganalisis {len(symbols)} saham dengan arah '{target_direction}', mohon tunggu...")

    from scripts.multi_tf import get_tf_analysis_v2, format_tf_analysis_v2

    for symbol in symbols:
        try:
            result, error = get_tf_analysis_v2(symbol, target_direction)
            if error:
                await update.message.reply_text(f"❌ {symbol}: {error}")
            elif result is None:
                await update.message.reply_text(f"❌ {symbol}: Gagal mendapatkan analisis.")
            else:
                # Dapatkan teks lengkap dari hasil
                full_text = format_tf_analysis_v2(result)
                # Kirim sebagai pesan terpisah
                await update.message.reply_text(full_text)
        except Exception as e:
            logger.exception(f"Error di tf_multi untuk {symbol}: {e}")
            await update.message.reply_text(f"❌ {symbol}: Error saat analisis.")

async def agent_multi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Analisis multi-agent untuk beberapa saham.
    Format: /agent_multi <kode1> <kode2> ...
    Contoh: /agent_multi BBCA BBRI TLKM
    Maksimal 5 saham per panggilan.
    """
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ Format: /agent_multi <kode1> <kode2> ...\n"
            "Contoh: /agent_multi BBCA BBRI TLKM\n"
            "Maksimal 5 saham per panggilan."
        )
        return

    # Batasi jumlah saham
    MAX_SYMBOLS = 5
    if len(context.args) > MAX_SYMBOLS:
        await update.message.reply_text(f"⚠️ Terlalu banyak saham. Maksimal {MAX_SYMBOLS} saham per panggilan.")
        return

    symbols = []
    for arg in context.args:
        raw = arg.upper()
        symbol = raw if raw.endswith('.JK') else raw + '.JK'
        symbols.append(symbol)

    await update.message.reply_text(f"⏳ Menganalisis {len(symbols)} saham dengan multi-agent, mohon tunggu...")

    # Impor fungsi yang diperlukan (sama seperti di agent_command)
    from scripts.analisis_adaptif import ambil_data_dari_db, tambah_indikator
    from scripts.regime_classifier import get_regime_classifier
    from scripts.multi_agent_selector import get_multi_agent

    for symbol in symbols:
        try:
            # Ambil data historis (100 hari)
            df = ambil_data_dari_db(symbol, hari=100)
            if df is None or len(df) < 50:
                await update.message.reply_text(f"❌ {symbol}: Data tidak cukup (minimal 50 hari).")
                continue

            df = tambah_indikator(df)

            # Deteksi regime
            classifier = get_regime_classifier()
            regime = classifier.predict_regime(df) if classifier.is_trained else "unknown"

            # Dapatkan multi-agent
            multi_agent = get_multi_agent()
            multi_agent.update_regime(regime)
            agent_signal, agent_confidence, details = multi_agent.get_consensus_signal(symbol, df)

            # Bangun pesan (sama seperti di agent_command)
            msg = f"🤖 *Multi-Agent Analysis {symbol}*\n"
            msg += f"Regime: {regime}\n\n"

            for d in details:
                direction = "BUY" if d.get('prob_up', 0) > d.get('prob_down', 0) else "SELL"
                msg += f"• {d['name']}: {direction} (conf {d['confidence']:.1f}%, reason: {d['reason'][:50]})\n"

            consensus_dir = "BUY" if agent_signal == 1 else "SELL" if agent_signal == -1 else "NETRAL"
            msg += f"\n*Konsensus:* {consensus_dir} (conf {agent_confidence:.1f}%)"

            # Kirim per saham
            await update.message.reply_text(msg)

        except Exception as e:
            logger.exception(f"Error di agent_multi untuk {symbol}: {e}")
            await update.message.reply_text(f"❌ {symbol}: Error saat analisis.")

async def train_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan status antrean training."""
    from scripts.training_queue import get_training_queue
    queue = get_training_queue()
    size = queue.get_queue_size()
    current = queue.get_current_tasks()
    await update.message.reply_text(
        f"📊 *Status Training*\n"
        f"Antrean: {size} task\n"
        f"Sedang berjalan: {current}"
    )


# ======================================================================
# DAFTARKAN HANDLER (gunakan application, bukan app)
# ======================================================================
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("status", status))
application.add_handler(CommandHandler("tanya", tanya))
application.add_handler(CommandHandler("jelas", jelas))
application.add_handler(CommandHandler("top", top))
application.add_handler(CommandHandler("screener", screener))
application.add_handler(CommandHandler("watchlist", watchlist))
application.add_handler(CommandHandler("watchlist_add", watchlist_add))
application.add_handler(CommandHandler("watchlist_remove", watchlist_remove))
application.add_handler(CommandHandler("watchlist_target", watchlist_target))
application.add_handler(CommandHandler("watchlist_stop", watchlist_stop))
application.add_handler(CommandHandler("tf", tf_command))
application.add_handler(CommandHandler("backtest", backtest))
application.add_handler(CommandHandler("evaluasi", evaluasi))
application.add_handler(CommandHandler("banding", banding))
application.add_handler(CommandHandler("calendar", calendar))
application.add_handler(CommandHandler("risk", risk_status))
application.add_handler(CommandHandler("set_cap", set_risk_cap))
application.add_handler(CommandHandler("walkforward", walkforward))
application.add_handler(CommandHandler("robust", robust))
application.add_handler(CommandHandler("journal", journal))
application.add_handler(CommandHandler("paper", paper_status))
application.add_handler(CommandHandler("paper_toggle", paper_toggle))
application.add_handler(CommandHandler("paper_reset", paper_reset))
application.add_handler(CommandHandler("optimize", optimize))
application.add_handler(CommandHandler("atr", atr_command))
application.add_handler(CommandHandler("econrisk", econ_risk))
application.add_handler(CommandHandler("econid", econid))
application.add_handler(CommandHandler("clusters", clusters))
application.add_handler(CommandHandler("clustersent", cluster_sentiment))
application.add_handler(CommandHandler("cooccur", cooccur))
application.add_handler(CommandHandler("import_status", import_status))
application.add_handler(CommandHandler("retrain", retrain))
application.add_handler(CommandHandler("clusters_update", clusters_update))
application.add_handler(CommandHandler("export", export))
application.add_handler(CommandHandler("mlreport", mlreport))
application.add_handler(CommandHandler("regime", regime_command))
application.add_handler(CommandHandler("agent", agent_command))
application.add_handler(CommandHandler("train_all", train_all))
application.add_handler(CommandHandler("update_econ", update_econ))
application.add_handler(CommandHandler("update_econid", update_econid))
application.add_handler(CommandHandler("train_regime", train_regime))
application.add_handler(CommandHandler("mlstatus", mlstatus))
application.add_handler(CommandHandler("errors", errors))  # opsional
application.add_handler(CommandHandler("rlstatus", rlstatus))
application.add_handler(CommandHandler("dqnstatus", dqnstatus))
application.add_handler(CommandHandler("sectors", sectors))
application.add_handler(CommandHandler("strategies", strategies))
application.add_handler(CommandHandler("weights", weights))
application.add_handler(CommandHandler("update_fundamental_all", update_fundamental_all_command))
application.add_handler(CommandHandler("update_historical", update_historical_command))
application.add_handler(CommandHandler("lstm_status", lstm_status))# train_xgb_watchlist.py
application.add_handler(CommandHandler("top5", top5_command))
application.add_handler(CommandHandler("evaluate_agents", evaluate_agents_command))
application.add_handler(CommandHandler("datacheck", datacheck_command))
application.add_handler(CommandHandler("jelas_multi", jelas_multi_command))
application.add_handler(CommandHandler("tf_multi", tf_multi_command))
application.add_handler(CommandHandler("agent_multi", agent_multi_command))
application.add_handler(CommandHandler("train_status", train_status))

# ======================================================================
# FUNGSI START BOT (jika dijalankan langsung)
# ======================================================================
def start_bot():
    print("🤖 Bot Telegram mulai berjalan. Kirim perintah ke bot Anda di Telegram.")
    application.run_polling()

if __name__ == "__main__":
    # Kode training hanya akan jalan jika file ini dieksekusi langsung, bukan saat diimpor
    watchlist = load_watchlist()
    symbols = [s for s in watchlist['symbols'] if s != 'BBCA.JK'][:5]
    for symbol in symbols:
        print(f"Training XGBoost untuk {symbol}...")
        try:
            train_advanced_model(symbol, target_days=5, tune=False)
        except Exception as e:
            print(f"Gagal: {e}")
    
    # start_bot()  # (opsional) jika ingin langsung menjalankan bot