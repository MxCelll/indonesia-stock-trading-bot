# scripts/historical_yahoo.py
import random
import yfinance as yf
import pandas as pd
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)
DB_PATH = 'data/saham.db'

def fetch_from_yahoo(symbol, start_date=None, end_date=None, days_back=365):
    """
    Mengambil data historis dari Yahoo Finance menggunakan yf.Ticker (menghindari MultiIndex).
    """
    try:
        # Tentukan rentang tanggal
        if end_date is None:
            end = datetime.now()
        else:
            end = datetime.strptime(end_date, '%Y-%m-%d')
        
        if start_date is None:
            start = end - timedelta(days=days_back)
        else:
            start = datetime.strptime(start_date, '%Y-%m-%d')
        
        logger.info(f"Mengambil data {symbol} dari Yahoo Finance...")
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end)
        
        if df.empty:
            logger.warning(f"Data kosong untuk {symbol}")
            return None
        
        # Reset index agar Date menjadi kolom
        df = df.reset_index()
        
        # Rename kolom (pastikan nama kolom sesuai)
        df = df.rename(columns={
            'Date': 'Date',
            'Open': 'Open',
            'High': 'High',
            'Low': 'Low',
            'Close': 'Close',
            'Volume': 'Volume'
        })
        
        # Pastikan kolom Date dalam format datetime
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Hanya ambil kolom yang diperlukan
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        
        logger.info(f"Berhasil mengambil {len(df)} baris untuk {symbol}")
        return df
        
    except Exception as e:
        logger.error(f"Yahoo Finance error untuk {symbol}: {e}")
        return None

def save_to_database(df, symbol):
    """Menyimpan DataFrame ke tabel saham dengan validasi."""
    try:
        # Validasi input
        if df is None or df.empty:
            logger.warning(f"Tidak ada data untuk disimpan untuk {symbol}")
            return False
        
        # Pastikan kolom yang diperlukan ada
        required_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required_columns):
            logger.error(f"Kolom tidak lengkap untuk {symbol}. Ada: {df.columns.tolist()}")
            return False
        
        # Pastikan kolom Date dalam format datetime
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        # Hapus baris dengan tanggal tidak valid
        df = df.dropna(subset=['Date'])
        if df.empty:
            logger.warning(f"Tidak ada data valid untuk {symbol} setelah membersihkan NaT")
            return False
        
        # Koneksi database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for _, row in df.iterrows():
            date_val = row['Date']
            if pd.isna(date_val):
                continue
            
            date_str = date_val.strftime('%Y-%m-%d')
            open_val = float(row['Open'])
            high_val = float(row['High'])
            low_val = float(row['Low'])
            close_val = float(row['Close'])
            volume_val = int(row['Volume'])
            
            cursor.execute('''
                INSERT OR REPLACE INTO saham (Date, Open, High, Low, Close, Volume, Symbol)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                date_str,
                open_val,
                high_val,
                low_val,
                close_val,
                volume_val,
                symbol
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Data {symbol} berhasil disimpan ke database ({len(df)} baris)")
        return True
        
    except Exception as e:
        logger.error(f"Gagal menyimpan {symbol} ke database: {e}")
        return False

def update_all_historical_parallel(symbols, days_back=365, max_workers=5, delay=1):
    """
    Update data historis secara paralel dengan maksimal max_workers thread.
    Jeda antar batch untuk menghindari pemblokiran IP.
    """
    success = 0
    total = len(symbols)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_symbol = {executor.submit(fetch_from_yahoo, sym, days_back=days_back): sym for sym in symbols}
        for i, future in enumerate(as_completed(future_to_symbol), 1):
            symbol = future_to_symbol[future]
            try:
                df = future.result()
                if df is not None and not df.empty:
                    if save_to_database(df, symbol):
                        success += 1
                else:
                    logger.warning(f"❌ Gagal mengambil data {symbol}")
            except Exception as e:
                logger.error(f"Error memproses {symbol}: {e}")
            if i % (max_workers * 2) == 0:
                time.sleep(delay)  # jeda berkala
    logger.info(f"Update paralel selesai: {success}/{total} berhasil.")
    return success, total

def update_all_historical(symbols, days_back=365, min_delay=4, max_delay=None, delay=None):
    """
    Memperbarui data historis untuk semua saham dalam daftar dengan jeda acak.
    
    Args:
        symbols: list kode saham (dengan .JK)
        days_back: jumlah hari data yang diambil (default 365)
        min_delay: batas bawah jeda acak (detik)
        max_delay: batas atas jeda acak (detik), jika None dan delay tidak None, maka sama dengan delay
        delay: jika diberikan, digunakan sebagai jeda tetap (menggantikan min_delay dan max_delay)
    
    Returns:
        tuple: (jumlah sukses, total)
    """
    # Menangani kompatibilitas dengan parameter delay (untuk update_all_stocks.py)
    if delay is not None:
        min_delay = delay
        max_delay = delay if max_delay is None else max_delay
    elif max_delay is None:
        max_delay = min_delay + 2  # nilai default jika hanya min_delay diberikan
    
    success = 0
    total = len(symbols)
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"({i}/{total}) Memproses {symbol}...")
        df = fetch_from_yahoo(symbol, days_back=days_back)
        
        if df is not None and not df.empty:
            if save_to_database(df, symbol):
                success += 1
        else:
            logger.warning(f"❌ Gagal mengambil data {symbol}")
        
        if i < total:
            # Gunakan jeda acak antara min_delay dan max_delay
            current_delay = random.uniform(min_delay, max_delay)
            logger.info(f"Menunggu {current_delay:.2f} detik...")
            time.sleep(current_delay)
    
    logger.info(f"Update selesai: {success}/{total} berhasil.")
    return success, total