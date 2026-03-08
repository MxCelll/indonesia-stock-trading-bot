# scripts/strategies.py
import pandas as pd

# Parameter default untuk strategi trend_swing (lebih longgar)
TREND_SWING_PARAMS = {
    'rsi_oversold': 40,        # sebelumnya 35
    'rsi_overbought': 60,       # sebelumnya 65
    'adx_threshold': 25,        # sebelumnya 30
    'use_ema_filter': True      # masih aktif
}

def trend_swing_signal(df, params=None):
    """
    Strategi untuk regime trending dengan parameter yang dapat disesuaikan.
    params: dict berisi 'rsi_oversold', 'rsi_overbought', 'adx_threshold', 'use_ema_filter'
    """
    if params is None:
        params = TREND_SWING_PARAMS

    rsi_os = params.get('rsi_oversold', 40)
    rsi_ob = params.get('rsi_overbought', 60)
    adx_th = params.get('adx_threshold', 25)
    use_ema = params.get('use_ema_filter', True)

    latest = df.iloc[-1]
    reasons = []

    if 'ADX' not in latest or pd.isna(latest['ADX']):
        return 0, "ADX tidak tersedia"

    adx = latest['ADX']
    di_plus = latest.get('DI_plus', 0)
    di_minus = latest.get('DI_minus', 0)

    # Sinyal tren (ADX kuat)
    if adx > adx_th:
        if di_plus > di_minus:
            reasons.append(f"ADX {adx:.1f} kuat, DI+ > DI-")
            if (not use_ema) or latest['Close'] > latest['EMA20']:
                return 1, "; ".join(reasons) + f" → BELI (tren naik) [ADX>{adx_th}]"
            else:
                reasons.append("harga di bawah EMA20, tunggu konfirmasi")
        elif di_minus > di_plus:
            reasons.append(f"ADX {adx:.1f} kuat, DI- > DI+")
            if (not use_ema) or latest['Close'] < latest['EMA20']:
                return -1, "; ".join(reasons) + f" → JUAL (tren turun) [ADX>{adx_th}]"
            else:
                reasons.append("harga di atas EMA20, tunggu konfirmasi")

    # Sinyal reversal (RSI ekstrem)
    if latest['RSI'] < rsi_os:
        reasons.append(f"RSI {latest['RSI']:.1f} < {rsi_os} (oversold)")
        if (not use_ema) or latest['Close'] > latest['EMA20']:
            return 1, "; ".join(reasons) + " → BELI (oversold bounce)"
    elif latest['RSI'] > rsi_ob:
        reasons.append(f"RSI {latest['RSI']:.1f} > {rsi_ob} (overbought)")
        if (not use_ema) or latest['Close'] < latest['EMA20']:
            return -1, "; ".join(reasons) + " → JUAL (overbought pullback)"

    return 0, "Tidak ada sinyal"

def gorengan_mode_signal(df, volume_factor=2.0, price_change_pct=3.0):
    """
    Strategi untuk volatilitas tinggi: volume spike dan harga bergerak >3%.
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None

    if prev is None:
        return 0, "Data kurang"

    volume_spike = latest['Volume'] > volume_factor * latest['Volume_MA20']
    price_up = (latest['Close'] - prev['Close']) / prev['Close'] > price_change_pct

    if volume_spike and price_up:
        return 1, f"Volume spike {volume_factor:.1f}x, harga naik {price_change_pct*100:.0f}%"

    price_down = (prev['Close'] - latest['Close']) / latest['Close'] > price_change_pct
    if price_down:
        return -1, f"Harga turun {price_change_pct*100:.0f}%, ambil profit"

    return 0, "Tidak ada sinyal"