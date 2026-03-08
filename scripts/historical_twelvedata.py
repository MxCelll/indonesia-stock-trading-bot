# scripts/historical_twelvedata.py
import requests
import pandas as pd
import logging
import sqlite3
import time
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
DB_PATH = 'data/saham.db'
CACHE_FILE = 'data/twelvedata_symbol_cache.json'

# Konstanta API
BASE_URL = "https://api.twelvedata.com"
API_KEY = os.getenv('TWELVEDATA_API_KEY')
if not API_KEY:
    raise ValueError("TWELVEDATA_API_KEY tidak ditemukan di file .env")

# Muat cache simbol dari file
def load_symbol_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_symbol_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

_symbol_cache = load_symbol_cache()

def search_symbol(keyword, exchange='IDX'):
    """
    Mencari simbol yang benar di Twelve Data menggunakan endpoint symbol_search.
    
    Args:
        keyword (str): Kode saham tanpa akhiran (misal: 'BBCA')
        exchange (str): Kode bursa (default 'IDX' untuk Indonesia)
    
    Returns:
        str atau None: Simbol yang benar (misal 'BBCA:IDX') atau None jika tidak ditemukan.
    """
    # Cek di cache terlebih dahulu
    cache_key = f"{keyword}_{exchange}"
    if cache_key in _symbol_cache:
        logger.info(f"Simbol {keyword} ditemukan di cache: {_symbol_cache[cache_key]}")
        return _symbol_cache[cache_key]
    
    url = f"{BASE_URL}/symbol_search"
    params = {
        'symbol': keyword,
        'exchange': exchange,
        'apikey': API_KEY
    }
    try:
        logger.info(f"Mencari simbol untuk {keyword} di exchange {exchange}...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data and len(data['data']) > 0:
            # Ambil simbol pertama yang paling relevan
            symbol = data['data'][0]['symbol']
            _symbol_cache[cache_key] = symbol
            save_symbol_cache(_symbol_cache)
            logger.info(f"Simbol ditemukan: {symbol}")
            return symbol
        else:
            logger.warning(f"Tidak ditemukan simbol untuk {keyword} di exchange {exchange}")
            return None
    except Exception as e:
        logger.error(f"Error saat mencari simbol {keyword}: {e}")
        return None

def fetch_historical(symbol_input, start_date=None, end_date=None, days_back=365):
    """
    Mengambil data historis harian dari Twelve Data.
    
    Args:
        symbol_input (str): Bisa berupa kode saham (dengan atau tanpa .JK) atau sudah dalam format yang benar.
        start_date (str): 'YYYY-MM-DD' (opsional)
        end_date (str): 'YYYY-MM-DD' (opsional)
        days_back (int): jumlah hari jika start_date tidak diberikan
    
    Returns:
        DataFrame dengan kolom Date, Open, High, Low, Close, Volume atau None
    """
    if not API_KEY:
        logger.error("API Key Twelve Data tidak ditemukan.")
        return None
    
    # Bersihkan input: hapus .JK jika ada, untuk pencarian
    clean_keyword = symbol_input.replace('.JK', '')
    
    # Coba cari simbol yang benar (hanya sekali, hasilnya akan di-cache)
    correct_symbol = search_symbol(clean_keyword, exchange='IDX')
    if not correct_symbol:
        # Jika pencarian gagal, coba beberapa format alternatif langsung
        alternatives = [
            clean_keyword,
            f"{clean_keyword}.JK",
            f"{clean_keyword}:IDX",
            f"IDX:{clean_keyword}",
            f"{clean_keyword}.IDX"
        ]
        logger.info(f"Pencarian gagal, mencoba format alternatif: {alternatives}")
        for alt in alternatives:
            df = try_fetch(alt, start_date, end_date, days_back)
            if df is not None:
                # Simpan ke cache agar tidak perlu mencoba lagi
                _symbol_cache[f"{clean_keyword}_IDX"] = alt
                save_symbol_cache(_symbol_cache)
                return df
        return None
    else:
        # Gunakan simbol yang benar
        return try_fetch(correct_symbol, start_date, end_date, days_back)

def try_fetch(symbol, start_date, end_date, days_back):
    """Fungsi internal untuk mencoba mengambil data dengan simbol tertentu."""
    if end_date is None:
        end = datetime.now()
    else:
        end = datetime.strptime(end_date, '%Y-%m-%d')
    
    if start_date is None:
        start = end - timedelta(days=days_back)
    else:
        start = datetime.strptime(start_date, '%Y-%m-%d')
    
    params = {
        'symbol': symbol,
        'interval': '1day',
        'apikey': API_KEY,
        'outputsize': days_back + 50,
        'format': 'JSON'
    }
    
    url = f"{BASE_URL}/time_series"
    
    try:
        logger.info(f"Fetching {symbol} from Twelve Data...")
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Cek error dari API
        if 'code' in data:
            logger.error(f"Twelve Data error untuk {symbol}: {data.get('message', 'Unknown error')}")
            return None
        
        if 'values' not in data:
            logger.warning(f"Tidak ada data untuk {symbol}")
            return None
        
        # Konversi ke DataFrame
        df = pd.DataFrame(data['values'])
        df = df.rename(columns={
            'datetime': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })
        
        # Filter berdasarkan rentang tanggal
        df['Date'] = pd.to_datetime(df['Date'])
        df = df[(df['Date'] >= start) & (df['Date'] <= end)]
        df = df.sort_values('Date')
        
        # Konversi tipe data
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        logger.info(f"Berhasil mengambil {len(df)} baris untuk {symbol}")
        return df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout saat mengambil {symbol}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error untuk {symbol}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error tidak terduga: {e}")
        return None

def save_to_database(df, symbol):
    """Menyimpan DataFrame ke tabel saham."""
    try:
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
        logger.info(f"Data {symbol} berhasil disimpan ke database ({len(df)} baris)")
        return True
    except Exception as e:
        logger.error(f"Gagal menyimpan {symbol} ke database: {e}")
        return False

def update_all_historical(symbols, days_back=365, delay=1.0):
    """
    Memperbarui data historis untuk semua saham dalam daftar.
    
    Args:
        symbols: list kode saham (dengan .JK, misal ['BBCA.JK', 'BBRI.JK'])
        days_back: jumlah hari data yang diambil (default 365)
        delay: jeda antar request (detik) untuk menghormati rate limit
    
    Returns:
        tuple: (jumlah sukses, total)
    """
    end = datetime.now()
    start = end - timedelta(days=days_back)
    start_str = start.strftime('%Y-%m-%d')
    end_str = end.strftime('%Y-%m-%d')
    
    success = 0
    total = len(symbols)
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"({i}/{total}) Memproses {symbol}...")
        df = fetch_historical(symbol, start_date=start_str, end_date=end_str, days_back=days_back)
        
        if df is not None and not df.empty:
            if save_to_database(df, symbol):
                success += 1
        else:
            logger.warning(f"❌ Gagal mengambil data {symbol}")
        
        if i < total:
            logger.info(f"Menunggu {delay} detik...")
            time.sleep(delay)
    
    logger.info(f"Update historical selesai: {success}/{total} berhasil.")
    return success, total