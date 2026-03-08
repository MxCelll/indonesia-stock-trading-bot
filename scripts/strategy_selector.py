# scripts/strategy_selector.py
import json
import os
import sqlite3
import pandas as pd
import ta
from scripts.market_regime import detect_regime, is_volatile_spike
from scripts.strategies import trend_swing_signal, gorengan_mode_signal
import logging
logger = logging.getLogger(__name__)

# File konfigurasi
OPTIMAL_PARAMS_FILE = 'data/optimal_params.json'
OPTIMAL_PARAMS_PER_REGIME_FILE = 'optimal_params_per_regime.json'

# Parameter default
DEFAULT_TREND_SWING_PARAMS = {
    'rsi_oversold': 35,
    'rsi_overbought': 65,
    'adx_threshold': 25,
    'use_ema_filter': True
}

def load_optimal_params():
    default = {
        'trend_swing': DEFAULT_TREND_SWING_PARAMS.copy(),
        'gorengan': {'volume_factor': 2.0, 'price_change_pct': 3.0}
    }
    if os.path.exists(OPTIMAL_PARAMS_FILE):
        with open(OPTIMAL_PARAMS_FILE, 'r') as f:
            data = json.load(f)
        # Pastikan kedua key ada
        for key in default:
            if key not in data:
                data[key] = default[key]
        return data
    else:
        return default

def save_optimal_params(params):
    os.makedirs('data', exist_ok=True)
    with open(OPTIMAL_PARAMS_FILE, 'w') as f:
        json.dump(params, f, indent=2)

def load_optimal_params_per_regime(symbol):
    """Memuat parameter per regime untuk simbol tertentu."""
    if os.path.exists(OPTIMAL_PARAMS_PER_REGIME_FILE):
        with open(OPTIMAL_PARAMS_PER_REGIME_FILE, 'r') as f:
            data = json.load(f)
        if symbol in data and 'trend_swing' in data[symbol]:
            return data[symbol]['trend_swing']
    return {}  # return empty dict jika tidak ada, nanti fallback ke default

def get_regime_for_signal(df_daily):
    """Mendapatkan regime pasar menggunakan GMM classifier."""
    from scripts.regime_classifier import get_regime_classifier
    classifier = get_regime_classifier()
    if classifier.is_trained:
        return classifier.predict_regime(df_daily)
    else:
        # fallback ke ADX
        adx_regime = detect_regime(df_daily)
        # mapping ADX ke nama regime GMM (sederhana)
        if adx_regime == 'trending':
            return 'trending_bull'  # asumsi, bisa juga dicek DI+
        elif adx_regime == 'sideways':
            return 'sideways'
        else:
            return 'high_volatility'

def get_weekly_indicators(symbol, db_path='data/saham.db'):
    conn = sqlite3.connect(db_path)
    query = f"""
    SELECT Date, Close FROM saham
    WHERE Symbol = '{symbol}'
    ORDER BY Date ASC
    """
    df = pd.read_sql(query, conn, parse_dates=['Date'])
    conn.close()
    if len(df) < 50:
        return None
    df.set_index('Date', inplace=True)
    weekly = df['Close'].resample('W-FRI').last().dropna().to_frame()
    weekly['EMA20'] = weekly['Close'].ewm(span=20, adjust=False).mean()
    weekly['RSI'] = ta.momentum.RSIIndicator(weekly['Close'], window=14).rsi()
    macd = ta.trend.MACD(weekly['Close'])
    weekly['MACD'] = macd.macd()
    weekly['MACD_signal'] = macd.macd_signal()
    latest = weekly.iloc[-1]
    return {
        'uptrend_ema': latest['Close'] > latest['EMA20'],
        'rsi': latest['RSI'],
        'macd_bullish': latest['MACD'] > latest['MACD_signal'],
        'price': latest['Close']
    }

def check_weekly_trend(symbol, db_path='data/saham.db'):
    weekly = get_weekly_indicators(symbol, db_path)
    if weekly is None:
        return True
    return weekly['uptrend_ema']

def get_signal(symbol, df_daily):
    # Deteksi regime dengan GMM
    regime = get_regime_for_signal(df_daily)
    
    # Muat parameter global
    global_params = load_optimal_params()
    
    # Muat parameter per regime untuk simbol ini
    params_per_regime = load_optimal_params_per_regime(symbol)
    
    # Tentukan parameter berdasarkan regime
    if regime in params_per_regime:
        params = params_per_regime[regime]
    else:
        params = global_params.get('trend_swing', DEFAULT_TREND_SWING_PARAMS)
    
    # 🔍 LOG: tampilkan regime dan params yang digunakan
    logger.info(f"Regime: {regime}, Params: {params}")
    
    # ... sisa kode ...
    # Pilih strategi berdasarkan regime
    if regime in ['trending_bull', 'trending_bear']:
        sig, reason = trend_swing_signal(df_daily, params=params)
        strategy_name = 'trend_swing'
    elif regime == 'high_volatility':
        # Gunakan gorengan mode, dengan parameter volume_factor jika ada di params
        vol_factor = params.get('volume_factor', global_params['gorengan']['volume_factor'])
        price_pct = params.get('price_change_pct', global_params['gorengan']['price_change_pct'])
        sig, reason = gorengan_mode_signal(df_daily, volume_factor=vol_factor, price_change_pct=price_pct)
        strategy_name = 'gorengan'
    else:  # sideways
        return 0, "Sideways, tidak trading", 'none'

    # Filter multi-timeframe: hanya untuk sinyal beli, cek weekly uptrend
    if sig == 1:
        weekly = get_weekly_indicators(symbol)
        if weekly is None:
            return 0, f"Data weekly tidak cukup, batalkan. {reason}", strategy_name
        if not (weekly['uptrend_ema'] and weekly['macd_bullish'] and weekly['rsi'] > 40):
            return 0, f"Filter weekly: EMA/MACD/RSI tidak mendukung. {reason}", strategy_name

    return sig, reason, strategy_name