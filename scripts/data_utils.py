# scripts/data_utils.py
import sqlite3
import pandas as pd
import ta
import logging
from scripts.indicators_advanced import ichimoku, add_fibonacci_columns

logger = logging.getLogger(__name__)

def ambil_data_dari_db(symbol, db_path='data/saham.db', hari=100):
    """Mengambil data historis dari database, membersihkan NaT, dan mengembalikan DataFrame."""
    conn = sqlite3.connect(db_path)
    query = f"""
    SELECT Date, Open, High, Low, Close, Volume
    FROM saham
    WHERE Symbol = '{symbol}'
    ORDER BY Date DESC
    LIMIT {hari}
    """
    df = pd.read_sql(query, conn, parse_dates=['Date'])
    conn.close()
    if df.empty:
        return None
    # Urutkan ascending
    df = df.sort_values('Date').reset_index(drop=True)
    # Hapus baris dengan NaT (tanggal invalid)
    df = df.dropna(subset=['Date'])
    if df.empty:
        logger.warning(f"Data untuk {symbol} kosong setelah membersihkan NaT")
        return None
    return df

def tambah_indikator(df, advanced=False):
    """Menambahkan indikator teknikal ke DataFrame.
       Jika advanced=True, tambahkan indikator Ichimoku dan Fibonacci."""
    df = df.copy()
    # RSI
    df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    # MACD
    macd = ta.trend.MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()
    df['MACD_diff'] = macd.macd_diff()
    # EMA
    df['EMA20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()
    df['EMA50'] = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
    df['EMA200'] = ta.trend.EMAIndicator(df['Close'], window=200).ema_indicator()
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
    df['BB_upper'] = bb.bollinger_hband()
    df['BB_middle'] = bb.bollinger_mavg()
    df['BB_lower'] = bb.bollinger_lband()
    # ATR
    df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
    # ADX
    adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=14)
    df['ADX'] = adx.adx()
    df['DI_plus'] = adx.adx_pos()
    df['DI_minus'] = adx.adx_neg()
    # Volume MA
    df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()

    if advanced:
        # Indikator lanjutan
        df = ichimoku(df)
        df = add_fibonacci_columns(df, period=100)

    # Isi NaN dengan forward fill lalu backward fill
    df = df.ffill().bfill()
    return df

def get_all_symbols(db_path='data/saham.db'):
    """Mengambil semua kode saham dari tabel symbols."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT symbol FROM symbols")
    symbols = [row[0] for row in cursor.fetchall()]
    conn.close()
    return symbols