# scripts/data_goapi.py
import requests
import pandas as pd
import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
GOAPI_KEY = os.getenv('GOAPI_KEY')
GOAPI_BASE_URL = "https://api.goapi.io"

logger = logging.getLogger(__name__)

# scripts/data_goapi.py (bagian fetch_historical_data)
def fetch_historical_data(symbol, start_date=None, end_date=None):
    """
    Mengambil data historis saham dari GoAPI.
    Endpoint: /stock/idx/{symbol}/historical?from={from}&to={to}
    """
    if not GOAPI_KEY:
        logger.error("GOAPI_KEY tidak ditemukan di .env.")
        return None

    clean_symbol = symbol.replace('.JK', '')
    
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    # Validasi rentang tanggal tidak lebih dari 365 hari
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    delta_days = (end_dt - start_dt).days
    if delta_days > 365:
        logger.warning(f"Rentang tanggal {delta_days} hari melebihi batas 365 hari. Memotong menjadi 365 hari terakhir.")
        start_dt = end_dt - timedelta(days=365)
        start_date = start_dt.strftime('%Y-%m-%d')

    endpoint = f"{GOAPI_BASE_URL}/stock/idx/{clean_symbol}/historical"
    headers = {'X-API-KEY': GOAPI_KEY, 'accept': 'application/json'}
    params = {'from': start_date, 'to': end_date}

    try:
        logger.info(f"Mengakses endpoint: {endpoint} dari {start_date} ke {end_date}")
        response = requests.get(endpoint, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get('status') == 'success' and 'data' in data and 'results' in data['data']:
            records = []
            for item in data['data']['results']:
                records.append({
                    'Date': item['date'],
                    'Open': float(item['open']),
                    'High': float(item['high']),
                    'Low': float(item['low']),
                    'Close': float(item['close']),
                    'Volume': int(item['volume'])
                })
            df = pd.DataFrame(records)
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            logger.info(f"Berhasil mengambil {len(df)} baris data untuk {symbol} dari GoAPI.")
            return df
        else:
            logger.error(f"Respons API tidak sesuai format: {data}")
            return None

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error: {e} - Response: {response.text}")
        return None
    except Exception as e:
        logger.exception(f"Error tidak terduga: {e}")
        return None

def fetch_realtime_prices(symbols):
    """
    Mengambil harga real-time untuk beberapa saham.
    Endpoint: /stock/idx/prices?symbols={symbols}
    
    Args:
        symbols (list): Daftar kode saham (contoh: ['BBCA', 'BBRI'])

    Returns:
        dict atau None.
    """
    if not GOAPI_KEY:
        logger.error("GOAPI_KEY tidak ditemukan.")
        return None

    # Bersihkan simbol
    clean_symbols = [s.replace('.JK', '') for s in symbols]
    symbols_str = ','.join(clean_symbols)

    endpoint = f"{GOAPI_BASE_URL}/stock/idx/prices"
    headers = {'X-API-KEY': GOAPI_KEY, 'accept': 'application/json'}
    params = {'symbols': symbols_str}

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'success' and 'data' in data and 'results' in data['data']:
            # Kembalikan dictionary dengan key symbol
            result_dict = {}
            for item in data['data']['results']:
                result_dict[item['symbol']] = {
                    'symbol': item['symbol'],
                    'price': float(item['close']),
                    'open': float(item['open']),
                    'high': float(item['high']),
                    'low': float(item['low']),
                    'volume': int(item['volume']),
                    'change': float(item['change']),
                    'change_pct': float(item['change_pct']),
                    'date': item['date']
                }
            return result_dict
        else:
            logger.error(f"Respons price tidak valid: {data}")
            return None
    except Exception as e:
        logger.exception(f"Error mengambil price: {e}")
        return None


# Fungsi fallback (jika perlu)
def get_historical_with_fallback(symbol, start_date=None, end_date=None):
    """
    Prioritas GoAPI, jika gagal fallback ke database (data lama).
    """
    df = fetch_historical_data(symbol, start_date, end_date)
    if df is not None and not df.empty:
        return df

    logger.warning(f"GoAPI gagal, fallback ke data database untuk {symbol}")
    from scripts.data_utils import ambil_data_dari_db
    df_fallback = ambil_data_dari_db(symbol, hari=365)
    return df_fallback