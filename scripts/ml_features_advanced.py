# scripts/ml_features_advanced.py
import pandas as pd
import numpy as np
import logging
from datetime import timedelta
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
from scripts.cluster_tracker import get_cluster_sentiment_for_symbol
# from scripts.sentiment_news import get_sentiment_for_period  # dinonaktifkan sementara

logger = logging.getLogger(__name__)

def add_technical_features(df):
    """Menambahkan fitur teknikal lanjutan ke dataframe."""
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
    # Price position relative to moving averages
    df['price_vs_sma20'] = df['Close'] / df['SMA20'] - 1
    df['price_vs_sma50'] = df['Close'] / df['SMA50'] - 1
    df['price_vs_ema20'] = df['Close'] / df['EMA20'] - 1
    
    # Rolling volatility
    for window in [5, 10, 20, 50]:
        df[f'volatility_{window}'] = df['Close'].pct_change().rolling(window).std()
    
    # Volume features
    df['volume_ratio'] = df['Volume'] / df['Volume_MA20']
    df['volume_change'] = df['Volume'].pct_change()
    
    # Price momentum
    for period in [1, 3, 5, 10, 20]:
        df[f'momentum_{period}'] = df['Close'] / df['Close'].shift(period) - 1
    
    # RSI features
    df['rsi_change'] = df['RSI'].diff()
    df['rsi_ma5'] = df['RSI'].rolling(5).mean()
    
    # MACD features
    df['macd_histogram'] = df['MACD'] - df['MACD_signal']
    df['macd_hist_change'] = df['macd_histogram'].diff()
    
    # ADX features
    df['adx_change'] = df['ADX'].diff()
    df['di_cross'] = (df['DI_plus'] - df['DI_minus']) / (df['DI_plus'] + df['DI_minus'] + 1e-9)
    
    # ATR features
    df['atr_ratio'] = df['ATR'] / df['Close']
    df['atr_change'] = df['ATR'].diff()
    
    return df

def add_microstructure_features(df):
    """Menambahkan fitur microstructure."""
    df['price_direction'] = np.sign(df['Close'].diff())
    df['volume_direction'] = df['price_direction'] * df['Volume']
    df['ofi'] = df['volume_direction'].rolling(window=5).sum() / df['Volume'].rolling(window=5).mean()
    
    df['vpin'] = (abs(df['volume_direction']) / df['Volume']) * df['volatility_5']
    
    df['quote_slope'] = df['Close'].diff() / (df['High'] - df['Low'] + 1e-9)
    
    df['tick_test'] = np.sign(df['Close'].diff()).fillna(0)
    
    df['weighted_volume'] = df['Volume'] * abs(df['Close'].pct_change())
    
    return df

def add_cross_asset_features(df, symbol):
    """Menambahkan fitur cross-asset (korelasi dengan IHSG)."""
    try:
        df_ihsg = ambil_data_dari_db('JKSE', hari=500)
        if df_ihsg is not None and len(df_ihsg) > 100:
            df_ihsg = df_ihsg.sort_values('Date')
            df = df.merge(df_ihsg[['Date', 'Close']], on='Date', how='left', suffixes=('', '_ihsg'))
            df['ihsg_return'] = df['Close_ihsg'].pct_change()
            df['corr_with_ihsg'] = df['Close'].rolling(20).corr(df['Close_ihsg'].rolling(20))
    except:
        pass
    return df

def add_cluster_sentiment_features(df, symbol):
    """Menambahkan fitur sentimen klaster (nilai tunggal untuk seluruh data)."""
    sentimen = get_cluster_sentiment_for_symbol(symbol)
    df['cluster_sentiment'] = sentimen
    return df

def add_sentiment_features(df, symbol, lookback_days=7):
    """
    Menambahkan fitur sentimen berita untuk setiap baris.
    Setiap baris menghitung rata-rata sentimen berita dalam lookback_days sebelumnya.
    Jika gagal (timeout/error), beri nilai default 0.
    """
    # Fungsi ini dinonaktifkan sementara untuk menghindari timeout
    df = df.copy()
    df['sentiment_score'] = 0.0
    return df

def create_features_advanced(symbol, lookback=30, target_days=5, use_economic=False, sentiment_lookback=7):
    """
    Membuat fitur lanjutan untuk model ML.
    
    Args:
        symbol: kode saham (dengan .JK)
        lookback: panjang window untuk pembuatan fitur (tidak digunakan langsung, tapi untuk konsistensi)
        target_days: jumlah hari ke depan yang diprediksi
        use_economic: apakah menggunakan data ekonomi (belum diimplementasikan)
        sentiment_lookback: jumlah hari ke belakang untuk mengambil berita
    
    Returns:
        X: array fitur
        y: array target (arah, 0/1)
        y_reg: array target (return persentase)
        feature_names: daftar nama fitur
        dates: array tanggal
    """
    # Ambil data historis minimal 800 hari
    df = ambil_data_dari_db(symbol, hari=800)
    if df is None or len(df) < 500:
        raise ValueError(f"Data tidak cukup untuk {symbol}")
    
    # Tambah indikator dasar (RSI, MACD, dll.)
    df = tambah_indikator(df)
    
    # Tambah fitur teknikal lanjutan
    df = add_technical_features(df)
    
    # Tambah fitur microstructure
    df = add_microstructure_features(df)
    
    # Tambah fitur cross-asset
    df = add_cross_asset_features(df, symbol)
    
    # Tambah fitur sentimen klaster (konstan per simbol)
    df = add_cluster_sentiment_features(df, symbol)
    
    # Tambah fitur sentimen berita per baris (dinonaktifkan sementara)
    # df = add_sentiment_features(df, symbol, lookback_days=sentiment_lookback)
    df['sentiment_score'] = 0.0  # Nilai default untuk menjaga konsistensi fitur
    
    # Urutkan berdasarkan tanggal
    df = df.sort_values('Date').reset_index(drop=True)
    
    # Buat target
    future_price = df['Close'].shift(-target_days)
    df['target_direction'] = (future_price > df['Close']).astype(int)
    df['target_return'] = (future_price / df['Close'] - 1) * 100
    
    # Hapus baris dengan NaN (karena perhitungan rolling, shift, dll.)
    df = df.dropna()
    
    # Pilih fitur numerik (kecuali kolom yang tidak diinginkan)
    exclude_cols = ['Date', 'Symbol', 'target_direction', 'target_return', 'Open', 'High', 'Low']
    feature_cols = [col for col in df.columns if col not in exclude_cols and np.issubdtype(df[col].dtype, np.number)]
    
    # Pastikan sentiment_score ada (jika tidak, tambahkan dengan nilai 0)
    if 'sentiment_score' not in df.columns:
        df['sentiment_score'] = 0.0
        if 'sentiment_score' not in feature_cols:
            feature_cols.append('sentiment_score')
    
    # Ambil nilai array
    X = df[feature_cols].values
    y = df['target_direction'].values
    y_reg = df['target_return'].values
    dates = df['Date'].values
    
    # Bersihkan nilai tak terhingga dan NaN (misalnya akibat pembagian dengan nol)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    
    logger.info(f"Fitur yang digunakan: {len(feature_cols)}")
    return X, y, y_reg, feature_cols, dates