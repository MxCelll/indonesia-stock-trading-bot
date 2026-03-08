# scripts/ensemble_predictor.py
import numpy as np
import pandas as pd
import joblib
import os
import logging
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb
import catboost as cb

# Konfigurasi logging
logger = logging.getLogger(__name__)
MODEL_DIR = 'data/ml_models'
os.makedirs(MODEL_DIR, exist_ok=True)

class EnsemblePredictor:
    """
    Ensemble dari XGBoost, LightGBM, dan CatBoost untuk prediksi arah harga.
    """
    def __init__(self, symbol, target_days=5):
        self.symbol = symbol
        self.target_days = target_days
        self.models = {}
        self.weights = {}
        self.scaler = None
        self.feature_cols = []
        self.load_or_train()

    def load_or_train(self):
        """Muat model jika sudah ada, jika tidak latih ensemble."""
        ensemble_path = os.path.join(MODEL_DIR, f"{self.symbol}_ensemble.pkl")
        if os.path.exists(ensemble_path):
            try:
                data = joblib.load(ensemble_path)
                self.models = data['models']
                self.weights = data['weights']
                self.scaler = data['scaler']
                self.feature_cols = data['feature_cols']
                logger.info(f"Ensemble untuk {self.symbol} dimuat.")
            except Exception as e:
                logger.warning(f"Gagal memuat ensemble untuk {self.symbol}: {e}. Melatih ulang...")
                self.train_ensemble()
        else:
            self.train_ensemble()

    def train_ensemble(self, lookback=30):
        """Latih ensemble menggunakan data historis."""
        try:
            from scripts.ml_features_advanced import create_features_advanced
        except ImportError:
            logger.error("Modul ml_features_advanced tidak ditemukan. Pastikan path sudah benar.")
            return

        try:
            X, y, _, feature_cols, _ = create_features_advanced(
                self.symbol, lookback=lookback, target_days=self.target_days
            )
        except Exception as e:
            logger.error(f"Gagal membuat fitur untuk {self.symbol}: {e}")
            return

        if len(X) == 0:
            logger.error(f"Tidak ada data fitur untuk {self.symbol}.")
            return

        # TimeSeriesSplit untuk validasi
        tscv = TimeSeriesSplit(n_splits=3)

        # Inisialisasi model
        xgb_model = xgb.XGBClassifier(
            objective='binary:logistic',
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )
        lgb_model = lgb.LGBMClassifier(
            objective='binary',
            random_state=42,
            verbose=-1
        )
        cat_model = cb.CatBoostClassifier(
            iterations=100,
            learning_rate=0.1,
            depth=6,
            random_seed=42,
            verbose=False
        )

        # Cross-validation untuk mencari bobot
        scores = {'xgb': [], 'lgb': [], 'cat': []}
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # Scale
            scaler_fold = StandardScaler()
            X_train_scaled = scaler_fold.fit_transform(X_train)
            X_val_scaled = scaler_fold.transform(X_val)

            # Latih masing-masing model
            xgb_model.fit(X_train_scaled, y_train)
            lgb_model.fit(X_train_scaled, y_train)
            cat_model.fit(X_train_scaled, y_train)

            # Evaluasi
            scores['xgb'].append(accuracy_score(y_val, xgb_model.predict(X_val_scaled)))
            scores['lgb'].append(accuracy_score(y_val, lgb_model.predict(X_val_scaled)))
            scores['cat'].append(accuracy_score(y_val, cat_model.predict(X_val_scaled)))

        # Hitung bobot berdasarkan akurasi rata-rata
        avg_scores = {k: np.mean(v) for k, v in scores.items()}
        total_score = sum(avg_scores.values())
        if total_score == 0:
            weights = {'xgb': 1/3, 'lgb': 1/3, 'cat': 1/3}
        else:
            weights = {k: v/total_score for k, v in avg_scores.items()}

        # Latih model akhir pada seluruh data
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        xgb_model.fit(X_scaled, y)
        lgb_model.fit(X_scaled, y)
        cat_model.fit(X_scaled, y)

        self.models = {
            'xgb': xgb_model,
            'lgb': lgb_model,
            'cat': cat_model
        }
        self.weights = weights
        self.feature_cols = feature_cols

        # Simpan ensemble
        ensemble_path = os.path.join(MODEL_DIR, f"{self.symbol}_ensemble.pkl")
        joblib.dump({
            'models': self.models,
            'weights': self.weights,
            'scaler': self.scaler,
            'feature_cols': self.feature_cols
        }, ensemble_path)
        logger.info(f"Ensemble untuk {self.symbol} disimpan dengan bobot: {weights}")

    def predict(self):
        """Prediksi dengan ensemble untuk kondisi terkini."""
        if not self.models:
            logger.error(f"Model ensemble untuk {self.symbol} belum dilatih.")
            return 0, 0

        try:
            from scripts.ml_features_advanced import create_features_advanced
            X, y, _, _, _ = create_features_advanced(
                self.symbol, lookback=30, target_days=self.target_days
            )
        except Exception as e:
            logger.error(f"Gagal membuat fitur saat prediksi untuk {self.symbol}: {e}")
            return 0, 0

        if len(X) == 0:
            logger.error(f"Tidak ada data fitur untuk prediksi {self.symbol}.")
            return 0, 0

        latest_features = X[-1].reshape(1, -1)
        latest_scaled = self.scaler.transform(latest_features)

        probas = {}
        for name, model in self.models.items():
            probas[name] = model.predict_proba(latest_scaled)[0]

        # Weighted average
        final_proba = np.zeros(2)
        for name, prob in probas.items():
            final_proba += self.weights[name] * prob
        # Normalisasi jika bobot tidak total 1 (misal karena pembulatan)
        final_proba /= sum(self.weights.values())

        direction = 1 if np.argmax(final_proba) == 1 else -1
        confidence = max(final_proba) * 100
        return direction, confidence

# Fungsi utilitas untuk mendapatkan predictor dengan fallback ke XGBoost
def get_ensemble_predictor(symbol):
    """
    Mengembalikan EnsemblePredictor jika tersedia, jika gagal fallback ke XGBoost biasa.
    """
    try:
        return EnsemblePredictor(symbol)
    except Exception as e:
        logger.warning(f"Gagal membuat ensemble untuk {symbol}: {e}. Fallback ke XGBoost.")
        from scripts.ml_predictor_advanced import get_predictor
        return get_predictor(symbol)

# Jika dijalankan langsung, lakukan test sederhana
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    predictor = get_ensemble_predictor('BBCA.JK')
    if predictor:
        direction, conf = predictor.predict()
        print(f"Prediksi: {direction}, Confidence: {conf}")