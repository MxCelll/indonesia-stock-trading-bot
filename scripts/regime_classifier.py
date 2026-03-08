# scripts/regime_classifier.py
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
import joblib
import os
import logging
from scripts.data_utils import ambil_data_dari_db, tambah_indikator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MarketRegimeClassifier:
    """
    Market regime classifier menggunakan Gaussian Mixture Models.
    Mendeteksi 4 regime: trending_bull, trending_bear, sideways, high_volatility.
    """
    
    def __init__(self, n_regimes=4, model_path='data/regime_model.pkl'):
        self.n_regimes = n_regimes
        self.model_path = model_path
        self.gmm = GaussianMixture(n_components=n_regimes, random_state=42, covariance_type='full')
        self.is_trained = False
        
        # Load model jika sudah ada
        if os.path.exists(model_path):
            try:
                self.gmm = joblib.load(model_path)
                self.is_trained = True
                logging.info("Model regime classifier dimuat dari disk.")
            except Exception as e:
                logging.warning(f"Gagal memuat model: {e}")
    
    def extract_features(self, df):
        """
        Ekstrak fitur untuk klasifikasi regime dari dataframe yang sudah memiliki indikator.
        """
        features = pd.DataFrame()
        features['volatility'] = df['ATR'] / df['Close']  # Volatilitas relatif
        features['volume_ratio'] = df['Volume'] / df['Volume_MA20']  # Rasio volume
        features['adx'] = df['ADX']  # Kekuatan tren
        features['rsi'] = df['RSI']  # Momentum
        features['trend_strength'] = abs(df['DI_plus'] - df['DI_minus']) / (df['DI_plus'] + df['DI_minus'] + 1e-9)  # Kekuatan arah
        features['price_position'] = (df['Close'] - df['EMA20']) / df['EMA20']  # Posisi harga relatif terhadap EMA20
        
        # Hapus baris dengan NaN
        return features.dropna()
    
    def train(self, symbols_list, lookback_days=500, max_symbols=10):
        """
        Latih GMM pada data historis beberapa saham.
        
        Parameters:
        symbols_list: daftar kode saham untuk training
        lookback_days: jumlah hari data yang digunakan per saham
        max_symbols: maksimal jumlah saham yang diproses (untuk efisiensi)
        """
        X_list = []
        
        for symbol in symbols_list[:max_symbols]:
            logging.info(f"Mengambil data untuk {symbol}...")
            df = ambil_data_dari_db(symbol, hari=lookback_days)
            if df is None or len(df) < 200:
                logging.warning(f"Data {symbol} tidak cukup, dilewati.")
                continue
            
            df = tambah_indikator(df)
            features = self.extract_features(df)
            if len(features) > 100:
                X_list.append(features.values)
        
        if not X_list:
            raise ValueError("Tidak ada data yang cukup untuk training.")
        
        X = np.vstack(X_list)
        logging.info(f"Total sampel training: {len(X)}")
        
        # Latih GMM
        self.gmm.fit(X)
        self.is_trained = True
        
        # Simpan model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.gmm, self.model_path)
        logging.info(f"Model disimpan di {self.model_path}")
        
        return True
    
    def predict_regime(self, df):
        """
        Prediksi regime untuk data terkini (baris terakhir df).
        Mengembalikan nama regime sebagai string.
        """
        if not self.is_trained:
            return 'unknown'
        
        features = self.extract_features(df)
        if len(features) == 0:
            return 'unknown'
        
        latest_features = features.iloc[-1].values.reshape(1, -1)
        
        # Cek NaN
        if np.isnan(latest_features).any():
            return 'unknown'
        
        regime = self.gmm.predict(latest_features)[0]
        
        # Mapping regime berdasarkan karakteristik (perlu disesuaikan setelah training)
        # Kita akan mapping berdasarkan nilai fitur rata-rata
        # Untuk sementara, kita gunakan mapping sederhana
        # Bisa diperbaiki dengan analisis lebih lanjut
        
        # Hitung rata-rata fitur untuk setiap komponen
        # Ini hanya contoh, bisa disesuaikan
        regime_names = {
            0: 'trending_bull',
            1: 'trending_bear', 
            2: 'sideways',
            3: 'high_volatility'
        }
        
        # Alternatif: mapping berdasarkan mean dari masing-masing komponen
        # Jika Anda ingin mapping yang lebih akurat, Anda bisa menganalisis mean dari setiap komponen
        # Setelah training, Anda bisa lihat mean_ dan sesuaikan.
        
        return regime_names.get(regime % self.n_regimes, 'unknown')
    
    def get_regime_description(self, regime_name):
        """Mengembalikan deskripsi singkat tentang regime."""
        descriptions = {
            'trending_bull': 'Pasar sedang dalam tren naik kuat. Cocok untuk strategi trend following.',
            'trending_bear': 'Pasar sedang dalam tren turun kuat. Disarankan menghindari posisi long.',
            'sideways': 'Pasar bergerak sideways. Strategi mean reversion lebih cocok.',
            'high_volatility': 'Volatilitas tinggi. Perkecil ukuran posisi dan perlebar stop loss.',
            'unknown': 'Tidak dapat menentukan regime.'
        }
        return descriptions.get(regime_name, 'Regime tidak dikenal.')

# Singleton instance untuk digunakan di seluruh aplikasi
_classifier_instance = None

def get_regime_classifier():
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = MarketRegimeClassifier()
    return _classifier_instance

def train_regime_classifier(symbols=None):
    """
    Fungsi utilitas untuk melatih classifier.
    Jika symbols=None, akan mengambil semua saham dari database.
    """
    if symbols is None:
        from scripts.data_utils import get_all_symbols
        symbols = get_all_symbols()
    
    classifier = get_regime_classifier()
    classifier.train(symbols, lookback_days=500, max_symbols=15)
    return classifier