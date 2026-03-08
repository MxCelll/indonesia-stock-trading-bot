# scripts/historical_investiny.py
import pandas as pd
import logging
import sqlite3
import time
from datetime import datetime, timedelta
import requests

# Coba import investiny
try:
    from investiny import historical_data, search_quotes
    INVESTINY_AVAILABLE = True
except ImportError:
    INVESTINY_AVAILABLE = False
    historical_data = None
    search_quotes = None
    print("⚠️ investiny tidak terinstall. Jalankan: pip install investiny")

logger = logging.getLogger(__name__)
DB_PATH = 'data/saham.db'

def fetch_from_investiny(symbol, start_date, end_date):
    """
    Mengambil data historis dari Investing.com via investiny dengan berbagai percobaan parameter.
    """
    if not INVESTINY_AVAILABLE:
        logger.error("investiny tidak tersedia.")
        return None
    
    try:
        # Bersihkan simbol
        clean_symbol = symbol.replace('.JK', '')
        
        # Konversi tanggal ke integer timestamp
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())
        
        # Percobaan 1: parameter symbol dengan timestamp integer
        try:
            data = historical_data(
                symbol=clean_symbol,
                from_date=start_ts,
                to_date=end_ts
            )
            if data and len(data) > 0:
                logger.info("investiny berhasil dengan parameter symbol (timestamp)")
                return _process_investiny_data(data, symbol)
        except Exception as e:
            logger.warning(f"Percobaan 1 gagal: {e}")
        
        # Percobaan 2: parameter ticker dengan timestamp integer
        try:
            data = historical_data(
                ticker=clean_symbol,
                from_date=start_ts,
                to_date=end_ts
            )
            if data and len(data) > 0:
                logger.info("investiny berhasil dengan parameter ticker (timestamp)")
                return _process_investiny_data(data, symbol)
        except Exception as e:
            logger.warning(f"Percobaan 2 gagal: {e}")
        
        # Percobaan 3: parameter symbol dengan tanggal string
        try:
            data = historical_data(
                symbol=clean_symbol,
                from_date=start_date,
                to_date=end_date
            )
            if data and len(data) > 0:
                logger.info("investiny berhasil dengan parameter symbol (string)")
                return _process_investiny_data(data, symbol)
        except Exception as e:
            logger.warning(f"Percobaan 3 gagal: {e}")
        
        # Percobaan 4: parameter ticker dengan tanggal string
        try:
            data = historical_data(
                ticker=clean_symbol,
                from_date=start_date,
                to_date=end_date
            )
            if data and len(data) > 0:
                logger.info("investiny berhasil dengan parameter ticker (string)")
                return _process_investiny_data(data, symbol)
        except Exception as e:
            logger.warning(f"Percobaan 4 gagal: {e}")
        
        # Jika semua gagal, coba cari dulu ticker yang benar dengan search_quotes
        try:
            search_results = search_quotes(clean_symbol)
            if search_results and len(search_results) > 0:
                # Ambil ticker yang benar dari hasil pencarian
                # Ini perlu disesuaikan dengan struktur hasil search_quotes
                # Misalnya, mungkin ada field 'ticker' atau 'symbol'
                # Untuk sementara, kita asumsikan hasil pertama adalah yang tepat
                # Dan kemudian coba lagi dengan ticker tersebut
                # Tapi ini agak rumit, kita lewati dulu
                pass
        except:
            pass
        
        logger.error(f"Semua percobaan investiny gagal untuk {symbol}")
        return None
        
    except Exception as e:
        logger.error(f"investiny gagal total untuk {symbol}: {e}")
        return None

def _process_investiny_data(data, symbol):
    """Memproses data mentah dari investiny menjadi DataFrame."""
    try:
        df = pd.DataFrame(data)
        if 'date' not in df.columns:
            logger.error("Kolom 'date' tidak ditemukan")
            return None
        
        df['Date'] = pd.to_datetime(df['date'])
        df = df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })
        required = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required):
            logger.error(f"Kolom tidak lengkap: {df.columns}")
            return None
        df = df[required].sort_values('Date')
        logger.info(f"investiny: {len(df)} baris untuk {symbol}")
        return df
    except Exception as e:
        logger.error(f"Gagal memproses data investiny: {e}")
        return None

def fetch_from_yfinance(symbol, start_date, end_date):
    """Fallback ke Yahoo Finance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)
        if df.empty:
            logger.warning(f"yfinance: Tidak ada data untuk {symbol}")
            return None
        df = df.reset_index()
        df = df.rename(columns={
            'Date': 'Date',
            'Open': 'Open',
            'High': 'High',
            'Low': 'Low',
            'Close': 'Close',
            'Volume': 'Volume'
        })
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        logger.info(f"yfinance: {len(df)} baris untuk {symbol}")
        return df
    except ImportError:
        logger.error("yfinance tidak terinstall")
        return None
    except Exception as e:
        logger.error(f"yfinance gagal untuk {symbol}: {e}")
        return None

def get_historical_data(symbol, start_date, end_date, prefer='investiny'):
    """
    Fungsi utama: prioritas investiny, fallback yfinance.
    """
    if prefer == 'investiny':
        df = fetch_from_investiny(symbol, start_date, end_date)
        if df is not None:
            return df
        logger.info(f"investiny gagal, coba yfinance...")
        return fetch_from_yfinance(symbol, start_date, end_date)
    else:
        df = fetch_from_yfinance(symbol, start_date, end_date)
        if df is not None:
            return df
        return fetch_from_investiny(symbol, start_date, end_date)

def save_to_database(df, symbol):
    """Menyimpan DataFrame ke tabel saham."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for _, row in df.iterrows():
            date_str = row['Date'].strftime('%Y-%m-%d') if hasattr(row['Date'], 'strftime') else str(row['Date'])
            cursor.execute('''
                INSERT OR REPLACE INTO saham (Date, Open, High, Low, Close, Volume, Symbol)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                date_str,
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                int(row['Volume']),
                symbol
            ))
        conn.commit()
        conn.close()
        logger.info(f"Data {symbol} berhasil disimpan ke database ({len(df)} baris)")
    except Exception as e:
        logger.error(f"Gagal menyimpan {symbol} ke database: {e}")

def update_all_historical(symbols, days_back=365, delay=1.0, prefer='investiny'):
    """
    Memperbarui data historis untuk semua saham dalam daftar.
    """
    end = datetime.now()
    start = end - timedelta(days=days_back)
    start_str = start.strftime('%Y-%m-%d')
    end_str = end.strftime('%Y-%m-%d')
    
    success = 0
    total = len(symbols)
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"({i}/{total}) Memproses {symbol}...")
        df = get_historical_data(symbol, start_str, end_str, prefer=prefer)
        
        if df is not None and not df.empty:
            save_to_database(df, symbol)
            success += 1
        else:
            logger.warning(f"❌ Gagal mengambil data {symbol}")
        
        if i < total:
            time.sleep(delay)
    
    logger.info(f"Update historical selesai: {success}/{total} berhasil.")
    return success, total

if __name__ == "__main__":
    # Pengujian
    logging.basicConfig(level=logging.INFO)
    symbol = 'BBCA.JK'
    print(f"Mencoba mengambil data {symbol}...")
    df = get_historical_data(symbol, '2025-01-01', '2026-02-28', prefer='investiny')
    if df is not None:
        print(df.head())
    else:
        print("investiny gagal, coba yfinance...")
        df = get_historical_data(symbol, '2025-01-01', '2026-02-28', prefer='yfinance')
        if df is not None:
            print(df.head())
        else:
            print("Semua sumber gagal. Mungkin perlu menggunakan GoAPI.")