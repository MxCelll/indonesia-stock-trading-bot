# scripts/fundamental_stockbit.py
import logging
from datetime import datetime
import os
import sys
import re
import yfinance as yf

# Tambahkan path proyek agar dapat mengimpor services dan utils
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from services.stockbit_api_client import StockbitApiClient

logger = logging.getLogger(__name__)

# Inisialisasi client global (agar autentikasi hanya sekali)
_stockbit_client = None

def get_stockbit_client():
    global _stockbit_client
    if _stockbit_client is None:
        _stockbit_client = StockbitApiClient()
    return _stockbit_client

def parse_value(value_str):
    """
    Mengubah string seperti '15.37', '20.44%', '118,573 B', '(33,691 B)' menjadi float.
    Menangani satuan B (miliar), M (juta), K (ribu), dan persen.
    """
    if not value_str or value_str == '-':
        return 0.0
    # Hapus spasi
    s = value_str.strip()
    # Tanda negatif dalam kurung
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    # Hapus koma
    s = s.replace(',', '')
    # Deteksi satuan
    multiplier = 1
    if s.endswith('B'):
        multiplier = 1_000_000_000
        s = s[:-1]
    elif s.endswith('M'):
        multiplier = 1_000_000
        s = s[:-1]
    elif s.endswith('K'):
        multiplier = 1_000
        s = s[:-1]
    # Hapus tanda persen
    s = s.replace('%', '')
    try:
        return float(s) * multiplier
    except ValueError:
        return 0.0

def find_value_by_keyword(items, keyword):
    """
    Mencari item dalam list of dict (dengan key 'fitem') yang memiliki 'name' mengandung keyword.
    Mengembalikan nilai yang sudah diparse, atau 0.0 jika tidak ditemukan.
    """
    for item in items:
        name = item.get('fitem', {}).get('name', '')
        if keyword.lower() in name.lower():
            value_str = item.get('fitem', {}).get('value', '0')
            return parse_value(value_str)
    return 0.0

def get_fundamental_from_stockbit(symbol):
    """
    Mengambil data fundamental dari StockBit menggunakan client yang sudah ada.
    """
    clean_symbol = symbol.replace('.JK', '')
    client = get_stockbit_client()
    
    url = f"https://exodus.stockbit.com/keystats/ratio/v1/{clean_symbol}?year_limit=10"
    try:
        response = client.get(url)
        if not response or 'data' not in response:
            logger.warning(f"Respons tidak valid untuk {symbol}: {response}")
            return None
        
        data = response['data']
        stats = data.get('stats', {})
        closure_items = data.get('closure_fin_items_results', [])
        
        # Inisialisasi hasil
        result = {
            'symbol': symbol,
            'per': 0.0,
            'pbv': 0.0,
            'roe': 0.0,
            'der': 0.0,
            'market_cap': parse_value(stats.get('market_cap', '0')),
            'dividend_yield': 0.0,
            'revenue': 0.0,
            'net_profit': 0.0,
            'updated_at': datetime.now().isoformat()
        }
        
        # Cari data di setiap closure item berdasarkan keystats_name
        for item in closure_items:
            keystats_name = item.get('keystats_name', '')
            fin_results = item.get('fin_name_results', [])
            
            if 'Current Valuation' in keystats_name:
                result['per'] = find_value_by_keyword(fin_results, 'PE Ratio (TTM)')
                result['pbv'] = find_value_by_keyword(fin_results, 'Price to Book Value')
            elif 'Management Effectiveness' in keystats_name:
                result['roe'] = find_value_by_keyword(fin_results, 'Return on Equity')
            elif 'Solvency' in keystats_name:
                result['der'] = find_value_by_keyword(fin_results, 'Debt to Equity Ratio')
            elif 'Dividend' in keystats_name:
                result['dividend_yield'] = find_value_by_keyword(fin_results, 'Dividend Yield')
            elif 'Income Statement' in keystats_name:
                result['revenue'] = find_value_by_keyword(fin_results, 'Revenue (TTM)')
                result['net_profit'] = find_value_by_keyword(fin_results, 'Net Income (TTM)')
        
        logger.info(f"Data fundamental untuk {symbol} berhasil diambil dari StockBit")
        return result
    except Exception as e:
        logger.exception(f"Error saat mengambil data dari StockBit: {e}")
        return None

def get_fundamental_from_yahoo(symbol):
    """
    Mengambil data fundamental dari Yahoo Finance sebagai fallback.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if not info:
            return None
        
        # Mapping field Yahoo ke format kita
        data = {
            'symbol': symbol,
            'per': info.get('trailingPE', 0) or info.get('forwardPE', 0) or 0,
            'pbv': info.get('priceToBook', 0),
            'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
            'der': info.get('debtToEquity', 0),
            'market_cap': info.get('marketCap', 0),
            'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
            'revenue': info.get('totalRevenue', 0),
            'net_profit': info.get('netIncomeToCommon', 0),
            'updated_at': datetime.now().isoformat()
        }
        # Bersihkan nilai None
        for k, v in data.items():
            if v is None:
                data[k] = 0
        return data
    except Exception as e:
        logger.error(f"Yahoo Finance fundamental error untuk {symbol}: {e}")
        return None