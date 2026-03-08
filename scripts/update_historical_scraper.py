# scripts/update_historical_scraper.py
import json
import logging
import time
from .scraper_investing import get_historical_data, save_to_database
from .data_utils import get_all_symbols
from .watchlist import load_watchlist

logger = logging.getLogger(__name__)

def load_slug_mapping():
    """Memuat mapping dari file JSON."""
    try:
        with open('data/slug_mapping.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("File data/slug_mapping.json tidak ditemukan.")
        return {}
    except Exception as e:
        logger.error(f"Gagal load mapping: {e}")
        return {}

def update_historical_all(use_watchlist=True, max_pages=3, delay=5):
    """
    Update data historis untuk semua saham.
    """
    mapping = load_slug_mapping()
    if not mapping:
        logger.error("Mapping kosong. Update dibatalkan.")
        return 0, 0
    
    if use_watchlist:
        symbols = load_watchlist().get('symbols', [])
        source = "watchlist"
    else:
        symbols = get_all_symbols()
        source = "seluruh database"
    
    # Filter hanya yang ada di mapping
    symbols_to_update = [s for s in symbols if s in mapping]
    logger.info(f"Ditemukan {len(symbols_to_update)} saham dengan mapping dari {source}.")
    
    success = 0
    for i, symbol in enumerate(symbols_to_update, 1):
        slug = mapping[symbol]
        logger.info(f"({i}/{len(symbols_to_update)}) Memproses {symbol} -> {slug}")
        
        df = get_historical_data(slug, max_pages=max_pages)
        if df is not None:
            if save_to_database(df, symbol):
                success += 1
        else:
            logger.warning(f"Gagal mengambil data untuk {symbol}")
        
        if i < len(symbols_to_update):
            logger.info(f"Menunggu {delay} detik...")
            time.sleep(delay)
    
    logger.info(f"Update selesai: {success}/{len(symbols_to_update)} berhasil.")
    return success, len(symbols_to_update)