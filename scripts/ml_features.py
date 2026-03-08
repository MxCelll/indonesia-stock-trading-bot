# scripts/ml_features.py
import pandas as pd
import numpy as np
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_features(symbol, lookback=30, target_days=5):
    """
    Membuat fitur dasar untuk model ML.
    Mengembalikan X, y, y_reg, feature_names, dates
    """
    # Ambil data historis (minimal 500 hari)
    df = ambil_data_dari_db(symbol, hari=800)
    if df is None or len(df) < 500:
        raise ValueError(f"Data tidak cukup untuk {symbol}")

    df = tambah_indikator(df)
    df = df.sort_values('Date').reset_index(drop=True)

    # Fitur teknikal sederhana
    feature_cols = [
        'RSI', 'MACD', 'MACD_signal', 'MACD_diff',
        'EMA20', 'EMA50', 'EMA200',
        'ADX', 'DI_plus', 'DI_minus',
        'ATR', 'Volume', 'Volume_MA20'
    ]
    # Pastikan semua kolom ada
    feature_cols = [col for col in feature_cols if col in df.columns]

    # Buat target: arah harga 5 hari ke depan
    future_price = df['Close'].shift(-target_days)
    df['target_direction'] = (future_price > df['Close']).astype(int)
    df['target_return'] = (future_price / df['Close'] - 1) * 100

    # Hapus baris dengan NaN
    df = df.dropna(subset=feature_cols + ['target_direction'])

    X = df[feature_cols].values
    y = df['target_direction'].values
    y_reg = df['target_return'].values
    dates = df['Date'].values

    logging.info(f"Fitur yang digunakan: {len(feature_cols)}")
    return X, y, y_reg, feature_cols, dates