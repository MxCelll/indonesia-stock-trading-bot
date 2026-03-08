# scripts/update_data_goapi.py
import logging
import sqlite3
from datetime import datetime, timedelta
from .data_goapi import fetch_historical_data
from .watchlist import load_watchlist

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = 'data/saham.db'

def update_all_symbols_from_goapi():
    watchlist_data = load_watchlist()
    symbols = watchlist_data['symbols']
    if not symbols:
        logger.warning("Watchlist kosong, tidak ada data diupdate.")
        return

    # Ambil 365 hari terakhir
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    for symbol in symbols:
        logger.info(f"Memproses {symbol}...")
        df = fetch_historical_data(symbol, start_date=start_str, end_date=end_str)
        if df is None or df.empty:
            logger.error(f"Gagal mengambil data {symbol} dari GoAPI.")
            continue

        # Simpan ke database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO saham (Date, Open, High, Low, Close, Volume, Symbol)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['Date'].strftime('%Y-%m-%d'),
                row['Open'],
                row['High'],
                row['Low'],
                row['Close'],
                int(row['Volume']),
                symbol
            ))
        conn.commit()
        conn.close()
        logger.info(f"Data {symbol} berhasil disimpan ({len(df)} baris).")

    logger.info("Update selesai.")

if __name__ == "__main__":
    update_all_symbols_from_goapi()