# scripts/indicators_advanced.py
import pandas as pd
import numpy as np

def ichimoku(df, tenkan_period=9, kijun_period=26, senkou_span_b_period=52):
    """
    Menghitung indikator Ichimoku Kinko Hyo.
    Input: df dengan kolom 'High', 'Low', 'Close'
    Output: DataFrame dengan kolom tambahan:
        - tenkan_sen
        - kijun_sen
        - senkou_span_a
        - senkou_span_b
        - chikou_span
        - senkou_span_a_shifted (26 periode ke depan)
        - senkou_span_b_shifted (26 periode ke depan)
    """
    df = df.copy()
    # Tenkan-sen (Conversion Line): (highest high + lowest low) / 2 over past 9 periods
    df['tenkan_sen'] = (df['High'].rolling(window=tenkan_period).max() + df['Low'].rolling(window=tenkan_period).min()) / 2

    # Kijun-sen (Base Line): (highest high + lowest low) / 2 over past 26 periods
    df['kijun_sen'] = (df['High'].rolling(window=kijun_period).max() + df['Low'].rolling(window=kijun_period).min()) / 2

    # Senkou Span A (Leading Span A): (tenkan_sen + kijun_sen) / 2, shifted forward by 26 periods
    df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(kijun_period)

    # Senkou Span B (Leading Span B): (highest high + lowest low) / 2 over past 52 periods, shifted forward by 26 periods
    df['senkou_span_b'] = ((df['High'].rolling(window=senkou_span_b_period).max() + df['Low'].rolling(window=senkou_span_b_period).min()) / 2).shift(kijun_period)

    # Chikou Span (Lagging Span): current close shifted backward by 26 periods
    df['chikou_span'] = df['Close'].shift(-kijun_period)

    return df

def add_fibonacci_columns(df, period=100):
    """
    Menambahkan kolom Fibonacci level ke setiap baris (berdasarkan lookback period).
    Level: 0, 0.236, 0.382, 0.5, 0.618, 0.786, 1
    """
    df = df.copy()
    fib_levels = ['fib_0', 'fib_0236', 'fib_0382', 'fib_05', 'fib_0618', 'fib_0786', 'fib_1']
    for col in fib_levels:
        df[col] = np.nan

    for i in range(period, len(df)):
        subset = df.iloc[i-period:i]
        high = subset['High'].max()
        low = subset['Low'].min()
        diff = high - low
        df.loc[df.index[i], 'fib_0'] = low
        df.loc[df.index[i], 'fib_0236'] = low + 0.236 * diff
        df.loc[df.index[i], 'fib_0382'] = low + 0.382 * diff
        df.loc[df.index[i], 'fib_05'] = low + 0.5 * diff
        df.loc[df.index[i], 'fib_0618'] = low + 0.618 * diff
        df.loc[df.index[i], 'fib_0786'] = low + 0.786 * diff
        df.loc[df.index[i], 'fib_1'] = high
    return df

def detect_pivot_points(df, lookback=20):
    """
    Mendeteksi pivot high dan pivot low.
    Mengembalikan tuple (pivot_highs, pivot_lows) dengan indeks dan harga.
    """
    pivot_highs = []
    pivot_lows = []
    for i in range(lookback, len(df) - lookback):
        # Pivot high: harga tertinggi di antara rentang lookback kiri dan kanan
        window_left = df['High'].iloc[i-lookback:i].max()
        window_right = df['High'].iloc[i+1:i+lookback+1].max()
        if df['High'].iloc[i] > window_left and df['High'].iloc[i] > window_right:
            pivot_highs.append((df.index[i], df['High'].iloc[i]))
        # Pivot low: harga terendah di antara rentang lookback kiri dan kanan
        window_left_low = df['Low'].iloc[i-lookback:i].min()
        window_right_low = df['Low'].iloc[i+1:i+lookback+1].min()
        if df['Low'].iloc[i] < window_left_low and df['Low'].iloc[i] < window_right_low:
            pivot_lows.append((df.index[i], df['Low'].iloc[i]))
    return pivot_highs, pivot_lows

def supply_demand_zones(df, lookback=20, min_touches=2, zone_width=0.005):
    """
    Mendeteksi zona supply dan demand berdasarkan pivot points.
    Mengembalikan list zona (level, kekuatan).
    """
    pivot_highs, pivot_lows = detect_pivot_points(df, lookback)
    # Kelompokkan pivot yang berdekatan menjadi zona
    # Sederhana: gunakan pivot sebagai level support/resistance
    # Kita bisa tambahkan logika clustering
    return {
        'supply_zones': [{'price': h[1], 'strength': 1} for h in pivot_highs],
        'demand_zones': [{'price': l[1], 'strength': 1} for l in pivot_lows]
    }