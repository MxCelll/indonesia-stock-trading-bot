import pandas as pd

def detect_regime(df, adx_threshold_trend=25, adx_threshold_sideways=20):
    """
    Mendeteksi regime pasar berdasarkan ADX.
    - trending: ADX > 25
    - sideways: ADX < 20
    - transisi: 20 <= ADX <= 25 (dianggap sideways)
    """
    latest = df.iloc[-1]
    adx = latest['ADX']

    if adx > adx_threshold_trend:
        return 'trending'
    elif adx < adx_threshold_sideways:
        return 'sideways'
    else:
        return 'sideways'

def is_volatile_spike(df, volume_factor=2.0, price_change_pct=3.0):
    """
    Deteksi kondisi gorengan: volume spike > 2x rata-rata dan pergerakan harga > 3%
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None

    if prev is None:
        return False

    volume_spike = latest['Volume'] > volume_factor * latest['Volume_MA20']
    price_move = abs((latest['Close'] - prev['Close']) / prev['Close'] * 100) > price_change_pct

    return volume_spike and price_move