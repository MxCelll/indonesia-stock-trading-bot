import sys
import os
import time
import threading
import asyncio
import schedule
import portalocker
from datetime import datetime
from scripts.notifier import set_bot_loop
...
bot_loop = asyncio.new_event_loop()
set_bot_loop(bot_loop)

# Tambahkan path folder scripts
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

# ==================== SINGLE INSTANCE LOCK ====================
LOCK_FILE = 'bot.lock'
lock_fd = None

def acquire_lock():
    global lock_fd
    try:
        lock_fd = open(LOCK_FILE, 'w')
        portalocker.lock(lock_fd, portalocker.LOCK_EX | portalocker.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        print(f"✅ Lock berhasil, PID {os.getpid()}")
        return True
    except portalocker.LockException:
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = f.read().strip()
            print(f"❌ Bot sudah berjalan dengan PID {pid}. Instance kedua akan ditutup.")
        except:
            print("❌ Bot sudah berjalan. Instance kedua akan ditutup.")
        return False
    except Exception as e:
        print(f"❌ Error saat lock: {e}")
        return False

def release_lock():
    global lock_fd
    if lock_fd:
        try:
            portalocker.unlock(lock_fd)
            lock_fd.close()
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
            print("✅ Lock file dibersihkan.")
        except Exception as e:
            print(f"⚠️ Error saat membersihkan lock: {e}")

# Cek apakah sudah ada instance lain
if not acquire_lock():
    sys.exit(1)

# ==================== LOGGING ====================
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def log_info(msg):
    logging.info(msg)
    sys.stdout.flush()

log_info("Memulai main.py...")


# ==================== IMPORT MODUL ====================
try:
    from weekly_report import send_weekly_report
    log_info("Import weekly_report OK")
except Exception as e:
    logging.exception("Gagal import weekly_report: %s", e)
    release_lock()
    sys.exit(1)

try:
    import telegram_bot
    application = telegram_bot.get_application()
    log_info("Import telegram_bot OK")
except Exception as e:
    logging.exception("Gagal import telegram_bot: %s", e)
    release_lock()
    sys.exit(1)

try:
    from market_calendar import is_market_open
    log_info("Import market_calendar OK")
except Exception as e:
    logging.exception("Gagal import market_calendar: %s", e)
    release_lock()
    sys.exit(1)

try:
    from notifier import set_bot_loop, kirim_notifikasi_sinkron
    log_info("Import notifier OK")
except Exception as e:
    logging.exception("Gagal import notifier: %s", e)
    release_lock()
    sys.exit(1)

try:
    from scripts.bot_utils import set_application
    log_info("Import bot_utils OK")
except Exception as e:
    logging.exception("Gagal import bot_utils: %s", e)
    release_lock()
    sys.exit(1)

try:
    from scripts.notifier_engine import run_notifier
    log_info("Import notifier_engine OK")
except Exception as e:
    logging.exception("Gagal import notifier_engine: %s", e)
    release_lock()
    sys.exit(1)

try:
    from scripts.economic_fetcher import get_fetcher as get_econ_fetcher
    log_info("Import economic_fetcher OK")
except Exception as e:
    logging.exception("Gagal import economic_fetcher: %s", e)
    release_lock()
    sys.exit(1)

try:
    from scripts.economic_indonesia import get_econ_fetcher as get_indonesia_econ_fetcher, get_holiday_fetcher
    log_info("Import economic_indonesia OK")
except Exception as e:
    logging.exception("Gagal import economic_indonesia: %s", e)
    release_lock()
    sys.exit(1)

try:
    from scripts.update_clusters import update_all_clusters
    log_info("Import update_clusters OK")
except Exception as e:
    logging.exception("Gagal import update_clusters: %s", e)
    release_lock()
    sys.exit(1)

try:
    from scripts.ml_train_advanced import train_all_advanced
    log_info("Import ml_train_advanced OK")
except Exception as e:
    logging.exception("Gagal import ml_train_advanced: %s", e)
    release_lock()
    sys.exit(1)

try:
    from scripts.train_rl import train_rl_orchestrator
    log_info("Import train_rl OK")
except Exception as e:
    logging.exception("Gagal import train_rl: %s", e)
    release_lock()
    sys.exit(1)

try:
    from scripts.auto_optimize import save_optimal_params_per_regime
    log_info("Import auto_optimize OK")
except Exception as e:
    logging.exception("Gagal import auto_optimize: %s", e)
    # Tidak fatal, hanya fitur tambahan
    pass

# ==================== SETUP APLIKASI ====================
set_application(application)
log_info("set_application OK")

bot_loop = None

# ==================== FUNGSI JOB ====================
def job_mingguan():
    log_info("Menjalankan job mingguan")
    kirim_notifikasi_sinkron("📈 Laporan Mingguan")
    if bot_loop:
        asyncio.run_coroutine_threadsafe(send_weekly_report(), bot_loop)

def job_notifikasi():
    if not is_market_open():
        return
    log_info(f"Menjalankan notifikasi jam {datetime.now().strftime('%H:%M')}")
    run_notifier()

def job_update_economic():
    log_info("Memulai update data ekonomi FRED...")
    fetcher = get_econ_fetcher()
    if fetcher.update_economic_data():
        log_info("Update data ekonomi FRED selesai")
    else:
        logging.error("Update data ekonomi FRED gagal")

def job_update_indonesia_economic():
    log_info("Memulai update data ekonomi Indonesia...")
    fetcher = get_indonesia_econ_fetcher()
    if fetcher.update_economic_data():
        log_info("Update data ekonomi Indonesia selesai")
    else:
        logging.error("Update data ekonomi Indonesia gagal")

def job_generate_strategies():
    logging.info("Memulai siklus pembuatan strategi untuk BBCA...")
    for symbol in ['BBCA.JK', 'BBRI.JK', 'TLKM.JK']:
        try:
            from scripts.strategy_generator import StrategyGenerator
            generator = StrategyGenerator(symbol)
            generator.run_generation_cycle(max_iterations=3)
            generator.close()
        except Exception as e:
            logging.error(f"Gagal untuk {symbol}: {e}")
    logging.info("Siklus pembuatan strategi selesai.")

def job_update_indonesia_holidays():
    log_info("Memulai update data libur nasional...")
    fetcher = get_holiday_fetcher()
    if fetcher.update_holidays():
        log_info("Update data libur nasional selesai")
    else:
        logging.error("Update data libur nasional gagal")

def job_update_all_fundamental():
    """Job untuk memperbarui data fundamental SEMUA saham di database."""
    logging.info("Memulai job update fundamental untuk SEMUA saham...")
    try:
        from scripts.fundamental import update_all_fundamental
        success, total = update_all_fundamental(use_watchlist=False, delay=1.5)
        logging.info(f"Job update semua saham selesai: {success}/{total} berhasil.")
    except Exception as e:
        logging.exception(f"Error job update semua saham: {e}")

def job_update_watchlist_fundamental():
    """Job untuk memperbarui data fundamental saham di WATCHLIST."""
    logging.info("Memulai job update fundamental untuk WATCHLIST...")
    try:
        from scripts.fundamental import update_all_fundamental
        success, total = update_all_fundamental(use_watchlist=True, delay=1.5)
        logging.info(f"Job update watchlist selesai: {success}/{total} berhasil.")
    except Exception as e:
        logging.exception(f"Error job update watchlist: {e}")

def job_update_sectors():
    logging.info("Memulai update data sektor...")
    from scripts.sector_rotation import get_sector_analyzer
    analyzer = get_sector_analyzer()
    analyzer.update_all_clusters()
    logging.info("Update data sektor selesai.")

def job_update_clusters():
    log_info("Memulai update klaster berita...")
    if update_all_clusters():
        log_info("Update klaster berita selesai")
    else:
        logging.error("Update klaster berita gagal")

def job_train_ml():
    log_info("Memulai training model ML untuk semua saham di watchlist...")
    try:
        train_all_advanced(use_watchlist=True, tune=True)
        log_info("Training model ML selesai")
    except Exception as e:
        logging.exception("Training model ML gagal: %s", e)

def job_update_parallel():
    logging.info("Memulai update data historis paralel...")
    from scripts.data_utils import get_all_symbols
    from scripts.historical_yahoo import update_all_historical_parallel
    symbols = get_all_symbols()
    update_all_historical_parallel(symbols, days_back=365, max_workers=5, delay=2)

def job_evaluate_agents():
    logging.info("Memulai evaluasi performa agen...")
    from scripts.evaluate_agents import evaluate_agent_performance, update_weights_from_performance
    results = evaluate_agent_performance(days_back=30)
    if results:
        update_weights_from_performance(results)
        logging.info("Bobot agen diperbarui.")
    else:
        logging.warning("Tidak ada data untuk evaluasi.")

def job_train_ensemble():
    logging.info("Memulai training ensemble untuk semua saham...")
    from scripts.watchlist import load_watchlist
    from scripts.ensemble_train import train_ensemble
    symbols = load_watchlist()['symbols']
    for symbol in symbols:
        try:
            train_ensemble(symbol, tune=False)
            logging.info(f"Ensemble untuk {symbol} selesai")
        except Exception as e:
            logging.exception(f"Gagal training ensemble {symbol}: {e}")

def job_update_historical_scraper():
    """Job untuk update data historis via scraper."""
    logging.info("Memulai job update historis (scraper)...")
    try:
        from scripts.scraper_investing import close_browser
        from scripts.update_historical_scraper import update_historical_all
        success, total = update_historical_all(use_watchlist=True, max_pages=3, delay=7)
        logging.info(f"Job scraper selesai: {success}/{total} berhasil.")
    except Exception as e:
        logging.exception(f"Error di job scraper: {e}")
    finally:
        close_browser()  # Pastikan browser ditutup

def job_update_historical():
    """Job untuk memperbarui data historical semua saham."""
    logging.info("Memulai job update data historical...")
    try:
        from scripts.data_utils import get_all_symbols
        from scripts.historical_investiny import update_all_historical
        
        symbols = get_all_symbols()
        if not symbols:
            logging.warning("Tidak ada saham di database.")
            return
        
        success, total = update_all_historical(symbols, days_back=365, delay=1.0)
        logging.info(f"Job update historical selesai: {success}/{total} berhasil.")
    except Exception as e:
        logging.exception(f"Error dalam job update historical: {e}")

def job_train_rl():
    log_info("Memulai training RL orchestrator...")
    try:
        train_rl_orchestrator(days_back=90)
        log_info("Training RL selesai")
    except Exception as e:
        logging.exception("Training RL gagal: %s", e)

def job_optimize_params_per_regime():
    logging.info("Memulai optimasi parameter per regime...")
    from scripts.watchlist import load_watchlist
    symbols = load_watchlist()['symbols']
    
    PARAM_GRID = [
        {'rsi_oversold': 30, 'rsi_overbought': 70, 'adx_threshold': 20, 'use_ema_filter': True},
        {'rsi_oversold': 35, 'rsi_overbought': 65, 'adx_threshold': 25, 'use_ema_filter': True},
        {'rsi_oversold': 40, 'rsi_overbought': 60, 'adx_threshold': 30, 'use_ema_filter': True},
        {'rsi_oversold': 30, 'rsi_overbought': 70, 'adx_threshold': 20, 'use_ema_filter': False},
        {'rsi_oversold': 35, 'rsi_overbought': 65, 'adx_threshold': 25, 'use_ema_filter': False},
        {'rsi_oversold': 40, 'rsi_overbought': 60, 'adx_threshold': 30, 'use_ema_filter': False},
    ]
    
    for symbol in symbols:
        try:
            save_optimal_params_per_regime(symbol, PARAM_GRID)
        except Exception as e:
            logging.exception(f"Gagal optimasi {symbol}: {e}")
    
    logging.info("Optimasi parameter per regime selesai.")

def jalankan_bot_telegram(loop):
    asyncio.set_event_loop(loop)
    log_info("Bot Telegram mulai polling...")
    application.run_polling()

# ==================== MAIN ====================
if __name__ == "__main__":
    try:
        log_info("Memasuki main block")
        bot_loop = asyncio.new_event_loop()
        set_bot_loop(bot_loop)
        log_info("bot_loop dibuat")

        t = threading.Thread(target=jalankan_bot_telegram, args=(bot_loop,), daemon=True)
        t.start()
        log_info("Thread bot dimulai")

        time.sleep(2)
        kirim_notifikasi_sinkron("Bot trading hidup dan siap (Mode Manual)!")
        log_info("Notifikasi startup dikirim")

        # ========== JADWAL TUGAS ==========
        schedule.every().sunday.at("10:00").do(job_mingguan)

        for hour in range(9, 17):
            schedule.every().day.at(f"{hour:02d}:00").do(job_notifikasi)
            schedule.every().day.at(f"{hour:02d}:30").do(job_notifikasi)

        schedule.every().day.at("01:00").do(job_update_economic)
        schedule.every().day.at("07:00").do(job_update_economic)
        schedule.every().day.at("13:00").do(job_update_economic)
        schedule.every().day.at("19:00").do(job_update_economic)

        schedule.every().day.at("06:00").do(job_update_sectors)
        schedule.every().day.at("02:00").do(job_update_indonesia_economic)
        schedule.every().day.at("02:30").do(job_update_indonesia_holidays)
        schedule.every().day.at("05:00").do(job_update_clusters)

        # Update semua saham setiap hari Minggu jam 03:00 (agar tidak terlalu sering)
        schedule.every().day.at("03:00").do(job_update_all_fundamental)

        # Update watchlist setiap hari jam 03:30 (data lebih segar untuk saham incaran)
        schedule.every().day.at("03:30").do(job_update_watchlist_fundamental)

        # Jadwalkan update data historical setiap hari jam 04:00
        schedule.every().day.at("04:00").do(job_update_historical)

        schedule.every().sunday.at("03:00").do(job_train_ml)
        schedule.every().sunday.at("04:00").do(job_train_rl)
        schedule.every().sunday.at("05:00").do(job_generate_strategies)
        schedule.every().sunday.at("06:00").do(job_optimize_params_per_regime)
        schedule.every().sunday.at("05:00").do(job_evaluate_agents)


        log_info("Scheduler berjalan. Tekan Ctrl+C untuk berhenti.")

        while True:
            schedule.run_pending()
            time.sleep(60)

    except KeyboardInterrupt:
        log_info("Menghentikan bot...")
        release_lock()
        sys.exit(0)
    except Exception as e:
        logging.exception("Error di main block: %s", e)
        release_lock()
        sys.exit(1)