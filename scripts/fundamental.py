# scripts/fundamental.py
import logging
import sqlite3
import time
from datetime import datetime

# Impor fungsi dari modul lain
from scripts.fundamental_stockbit import get_fundamental_from_stockbit
from scripts.watchlist import load_watchlist
from scripts.data_utils import get_all_symbols
from scripts.fundamental_stockbit import get_fundamental_from_stockbit, get_fundamental_from_yahoo

logger = logging.getLogger(__name__)
logger.info("fundamental.py: mulai")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_fundamental_cache = {}
DB_PATH = 'data/saham.db'

def _ensure_table():
    """Memastikan tabel fundamental_data ada dengan kolom yang diperlukan."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fundamental_data (
            symbol TEXT PRIMARY KEY,
            per REAL,
            pbv REAL,
            roe REAL,
            der REAL,
            market_cap REAL,
            dividend_yield REAL,
            revenue REAL,
            net_profit REAL,
            updated_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def _get_from_database(symbol):
    """Mengambil data fundamental dari database lokal."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT per, pbv, roe, der, market_cap, dividend_yield, revenue, net_profit, updated_at
        FROM fundamental_data WHERE symbol = ?
    ''', (symbol,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'symbol': symbol,
            'per': row[0],
            'pbv': row[1],
            'roe': row[2],
            'der': row[3],
            'market_cap': row[4],
            'dividend_yield': row[5],
            'revenue': row[6],
            'net_profit': row[7],
            'updated_at': row[8]
        }
    return None

def _save_to_database(data):
    """Menyimpan data fundamental ke database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO fundamental_data
        (symbol, per, pbv, roe, der, market_cap, dividend_yield, revenue, net_profit, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['symbol'],
        data['per'],
        data['pbv'],
        data['roe'],
        data['der'],
        data['market_cap'],
        data['dividend_yield'],
        data['revenue'],
        data['net_profit'],
        data['updated_at']
    ))
    conn.commit()
    conn.close()

def parse_currency_to_float(value_str):
    """Helper untuk mengubah string mata uang (dengan koma) menjadi float."""
    if not value_str:
        return 0.0
    try:
        return float(value_str.replace(',', ''))
    except (ValueError, AttributeError):
        return 0.0

def get_fundamental_data(symbol, force_refresh=False):
    """
    Mengambil data fundamental dengan urutan:
    1. Cache
    2. Database lokal
    3. StockBit API
    4. Yahoo Finance (fallback)
    5. Data dummy
    """
    if not force_refresh and symbol in _fundamental_cache:
        return _fundamental_cache[symbol]
    
    # Coba dari database
    data = _get_from_database(symbol)
    if data and any(data.get(k, 0) > 0 for k in ['per', 'pbv', 'roe']):
        _fundamental_cache[symbol] = data
        return data
    
    # Jika tidak ada atau tidak valid, coba dari StockBit
    logger.info(f"Mencoba mengambil data fundamental untuk {symbol} dari StockBit...")
    from scripts.fundamental_stockbit import get_fundamental_from_stockbit
    data = get_fundamental_from_stockbit(symbol)
    if data and any(data.get(k, 0) > 0 for k in ['per', 'pbv', 'roe']):
        _save_to_database(data)
        _fundamental_cache[symbol] = data
        return data
    
    # Jika StockBit gagal, coba Yahoo Finance
    logger.info(f"StockBit gagal, mencoba Yahoo Finance untuk {symbol}...")
    from scripts.fundamental_stockbit import get_fundamental_from_yahoo
    data = get_fundamental_from_yahoo(symbol)
    if data and any(data.get(k, 0) > 0 for k in ['per', 'pbv', 'roe']):
        _save_to_database(data)
        _fundamental_cache[symbol] = data
        return data
    
    # Fallback ke data dummy
    logger.warning(f"Semua sumber gagal, menggunakan data dummy untuk {symbol}")
    data = get_fallback_fundamental(symbol)
    if data:
        _fundamental_cache[symbol] = data
        return data
    
    return None

def fetch_and_save_fundamental(symbol):
    """
    Memaksa pengambilan data baru dari StockBit dan menyimpannya.
    Mengembalikan True jika berhasil, False jika gagal.
    """
    data = get_fundamental_from_stockbit(symbol)
    if data and any(data.get(k, 0) > 0 for k in ['per', 'pbv', 'roe']):
        _save_to_database(data)
        _fundamental_cache[symbol] = data
        return True
    return False

def get_fallback_fundamental(symbol):
    """
    Fallback ke data dummy jika semua sumber gagal.
    """
    dummy_data = {
        'BBCA.JK': {'per': 18.5, 'pbv': 2.8, 'roe': 22.5, 'der': 1.2, 'market_cap': 850_000_000_000_000, 'dividend_yield': 2.1},
        'BBRI.JK': {'per': 12.3, 'pbv': 1.9, 'roe': 18.7, 'der': 1.8, 'market_cap': 620_000_000_000_000, 'dividend_yield': 3.5},
        'BMRI.JK': {'per': 11.8, 'pbv': 1.7, 'roe': 17.2, 'der': 1.5, 'market_cap': 480_000_000_000_000, 'dividend_yield': 3.2},
        'TLKM.JK': {'per': 14.2, 'pbv': 2.1, 'roe': 19.3, 'der': 0.8, 'market_cap': 320_000_000_000_000, 'dividend_yield': 4.1},
        'ASII.JK': {'per': 10.5, 'pbv': 1.3, 'roe': 15.8, 'der': 0.6, 'market_cap': 280_000_000_000_000, 'dividend_yield': 2.8},
        'GGRM.JK': {'per': 8.2, 'pbv': 0.9, 'roe': 12.4, 'der': 0.4, 'market_cap': 95_000_000_000_000, 'dividend_yield': 5.2},
        'ESTI.JK': {'per': 14.0, 'pbv': 1.9, 'roe': 17.0, 'der': 0.9, 'market_cap': 2_500_000_000_000, 'dividend_yield': 1.5},
        # Anda bisa menambahkan saham lain di sini
    }
    result = dummy_data.get(symbol)
    if result:
        logger.warning(f"Menggunakan data dummy untuk {symbol}")
    return result

def enrich_with_fundamental(symbol, df_teknikal=None, force_refresh=False):
    """
    Menggabungkan data fundamental ke dalam analisis.
    """
    fundamental = get_fundamental_data(symbol, force_refresh)
    if fundamental is None:
        return None
    
    # Tambahkan kolom fundamental ke DataFrame jika ada
    if df_teknikal is not None and not df_teknikal.empty:
        for key, value in fundamental.items():
            if key not in ['symbol', 'updated_at']:
                df_teknikal[key] = value
    
    return fundamental

def fundamental_score(fundamental):
    """
    Menghitung skor fundamental (0-100) - fungsi ini TIDAK BERUBAH.
    Menggunakan logika yang sama seperti sebelumnya.
    """
    if fundamental is None:
        return 50, "Data fundamental tidak tersedia"
    
    score = 0
    reasons = []
    
    # PER
    per = fundamental.get('per', 0)
    if per > 0:
        if per < 10:
            score += 30
            reasons.append(f"PER rendah ({per:.1f}x) [+30]")
        elif per < 15:
            score += 20
            reasons.append(f"PER cukup ({per:.1f}x) [+20]")
        elif per < 25:
            score += 10
            reasons.append(f"PER moderat ({per:.1f}x) [+10]")
        else:
            score -= 10
            reasons.append(f"PER tinggi ({per:.1f}x) [-10]")
    else:
        reasons.append("PER tidak tersedia")
    
    # PBV
    pbv = fundamental.get('pbv', 0)
    if pbv > 0:
        if pbv < 1:
            score += 20
            reasons.append(f"PBV < 1, undervalued ({pbv:.2f}x) [+20]")
        elif pbv < 2:
            score += 15
            reasons.append(f"PBV wajar ({pbv:.2f}x) [+15]")
        elif pbv < 3:
            score += 5
            reasons.append(f"PBV agak tinggi ({pbv:.2f}x) [+5]")
        else:
            score -= 10
            reasons.append(f"PBV tinggi ({pbv:.2f}x) [-10]")
    else:
        reasons.append("PBV tidak tersedia")
    
    # ROE
    roe = fundamental.get('roe', 0)
    if roe > 0:
        if roe > 20:
            score += 25
            reasons.append(f"ROE sangat baik ({roe:.1f}%) [+25]")
        elif roe > 15:
            score += 20
            reasons.append(f"ROE baik ({roe:.1f}%) [+20]")
        elif roe > 10:
            score += 10
            reasons.append(f"ROE cukup ({roe:.1f}%) [+10]")
        else:
            score += 5
            reasons.append(f"ROE rendah ({roe:.1f}%) [+5]")
    else:
        reasons.append("ROE tidak tersedia")
    
    # DER
    der = fundamental.get('der', 0)
    if der > 0:
        if der < 0.5:
            score += 15
            reasons.append(f"DER sangat rendah ({der:.2f}x) [+15]")
        elif der < 1:
            score += 10
            reasons.append(f"DER rendah ({der:.2f}x) [+10]")
        elif der < 2:
            score += 5
            reasons.append(f"DER moderat ({der:.2f}x) [+5]")
        else:
            score -= 10
            reasons.append(f"DER tinggi ({der:.2f}x) [-10]")
    else:
        reasons.append("DER tidak tersedia")
    
    # Dividend Yield
    div = fundamental.get('dividend_yield', 0)
    if div > 0:
        if div > 5:
            score += 10
            reasons.append(f"Dividen tinggi ({div:.1f}%) [+10]")
        elif div > 3:
            score += 5
            reasons.append(f"Dividen cukup ({div:.1f}%) [+5]")
        else:
            score += 2
            reasons.append(f"Dividen kecil ({div:.1f}%) [+2]")
    else:
        reasons.append("Dividen tidak ada")
    
    return score, "; ".join(reasons)

def update_all_fundamental(use_watchlist=False, delay=1.5):
    """
    Memperbarui data fundamental untuk seluruh saham di database atau watchlist.
    
    Args:
        use_watchlist (bool): Jika True, update hanya saham di watchlist.
                              Jika False, update semua saham di database.
        delay (float): Jeda antar request (detik) untuk menghindari banjir request.
    
    Returns:
        tuple: (jumlah sukses, total)
    """
    # Tentukan sumber simbol
    if use_watchlist:
        watchlist_data = load_watchlist()
        symbols = watchlist_data.get('symbols', [])
        source = "watchlist"
    else:
        symbols = get_all_symbols()
        source = "seluruh database"
    
    if not symbols:
        logger.warning(f"Tidak ada saham di {source} untuk diupdate.")
        return 0, 0
    
    total = len(symbols)
    success_count = 0
    logger.info(f"Memulai update fundamental untuk {total} saham dari {source}...")
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"({i}/{total}) Memproses {symbol}...")
        if fetch_and_save_fundamental(symbol):
            success_count += 1
            logger.info(f"✅ {symbol} berhasil diupdate.")
        else:
            logger.warning(f"❌ {symbol} gagal diupdate.")
        
        # Jeda antar request, kecuali untuk yang terakhir
        if i < total:
            time.sleep(delay)
    
    logger.info(f"Update fundamental selesai: {success_count}/{total} berhasil.")
    return success_count, total

# Pastikan tabel ada saat modul dimuat
_ensure_table()