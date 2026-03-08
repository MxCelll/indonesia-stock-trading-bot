# scripts/fundamental_fetcher.py
import requests
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Optional, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StockBitFundamentalFetcher:
    """
    Fetcher untuk data fundamental dari StockBit API (gratis).
    Mengambil data dari endpoint publik StockBit.
    """
    
    # Base URL untuk StockBit API (perlu disesuaikan dari hasil riset)
    BASE_URL = "https://stockbit.com/api/v2"  # contoh, mungkin berbeda
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        })
    
    def get_fundamental_data(self, symbol: str) -> Optional[Dict]:
        """
        Mengambil data fundamental dari StockBit API.
        symbol: format 'BBCA.JK' (dengan .JK)
        """
        try:
            clean_symbol = symbol.replace('.JK', '')
            # Endpoint perlu disesuaikan dengan hasil penelitian dari repositori
            # Contoh: /stock/{symbol}/fundamental
            url = f"{self.BASE_URL}/stock/{clean_symbol}/fundamental"
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                logging.warning(f"Gagal mengambil data untuk {symbol}: HTTP {response.status_code}")
                return None
            data = response.json()
            
            # Asumsikan respons JSON memiliki field: data yang berisi informasi fundamental
            # Misalnya: data['data']['pe'], data['data']['pbv'], dll. Sesuaikan dengan dokumentasi
            if data.get('status') != 'ok' or 'data' not in data:
                logging.warning(f"Respons tidak valid untuk {symbol}: {data}")
                return None
            
            fund = data['data']
            fundamental = {
                'symbol': symbol,
                'per': fund.get('pe', 0),
                'pbv': fund.get('pbv', 0),
                'roe': fund.get('roe', 0),
                'der': fund.get('der', 0),
                'market_cap': fund.get('market_cap', 0),
                'dividend_yield': fund.get('dividend_yield', 0),
                'revenue': fund.get('revenue', 0),
                'net_profit': fund.get('net_profit', 0),
                'updated_at': datetime.now().isoformat()
            }
            return fundamental
        except requests.exceptions.Timeout:
            logging.error(f"Timeout saat mengambil data {symbol}")
            return None
        except Exception as e:
            logging.error(f"Error mengambil data {symbol}: {e}")
            return None
    
    def save_to_database(self, fundamental: Dict, db_path: str = 'data/saham.db'):
        """
        Menyimpan data fundamental ke database.
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Buat tabel jika belum ada
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
        
        cursor.execute('''
            INSERT OR REPLACE INTO fundamental_data 
            (symbol, per, pbv, roe, der, market_cap, dividend_yield, revenue, net_profit, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fundamental['symbol'],
            fundamental['per'],
            fundamental['pbv'],
            fundamental['roe'],
            fundamental['der'],
            fundamental['market_cap'],
            fundamental['dividend_yield'],
            fundamental['revenue'],
            fundamental['net_profit'],
            fundamental['updated_at']
        ))
        conn.commit()
        conn.close()
        logging.info(f"Data fundamental {fundamental['symbol']} berhasil disimpan")
    
    def get_from_database(self, symbol: str, db_path: str = 'data/saham.db') -> Optional[Dict]:
        """
        Mengambil data fundamental dari database.
        """
        conn = sqlite3.connect(db_path)
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
    
    def update_all_symbols(self, symbols: List[str]) -> List[str]:
        """
        Memperbarui data fundamental untuk daftar simbol.
        """
        results = []
        for symbol in symbols:
            logging.info(f"Memproses {symbol}...")
            data = self.get_fundamental_data(symbol)
            if data and any(value != 0 for key, value in data.items() if key not in ['symbol', 'updated_at']):
                self.save_to_database(data)
                results.append(symbol)
            else:
                logging.warning(f"Gagal mendapatkan data valid untuk {symbol}")
        logging.info(f"Update selesai: {len(results)}/{len(symbols)} berhasil")
        return results

# Singleton instance
_fetcher_instance = None

def get_fetcher():
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = StockBitFundamentalFetcher()
    return _fetcher_instance