# scripts/ml_predictor_advanced.py
import numpy as np
import pandas as pd
import joblib
import os
import json
import logging
from scripts.ml_features_advanced import create_features_advanced
from scripts.data_utils import ambil_data_dari_db, tambah_indikator

logger = logging.getLogger(__name__)
logger.info("ml_predictor_advanced.py: mulai")

MODEL_DIR = 'data/ml_models'
REPORT_DIR = 'data/ml_reports'

class MLPredictorAdvanced:
    def __init__(self, symbol, target_days=5, use_tuned=True):
        self.symbol = symbol
        self.target_days = target_days
        
        if use_tuned:
            model_name = f"{symbol}_xgb_tuned_{target_days}d.pkl"
            scaler_name = f"{symbol}_scaler_tuned_{target_days}d.pkl"
        else:
            model_name = f"{symbol}_xgb_adv_{target_days}d.pkl"
            scaler_name = f"{symbol}_scaler_adv_{target_days}d.pkl"
        
        model_path = os.path.join(MODEL_DIR, model_name)
        scaler_path = os.path.join(MODEL_DIR, scaler_name)
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model untuk {symbol} belum dilatih. Jalankan ml_train_advanced.py dulu.")
        
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
    
    def predict(self):
        """
        Menghasilkan prediksi untuk kondisi terkini.
        Returns: direction (1 naik, -1 turun), confidence (0-100)
        """
        try:
            X, y, _, feature_names, dates = create_features_advanced(self.symbol, lookback=30, target_days=self.target_days)
        except Exception as e:
            logger.error(f"Error membuat fitur: {e}")
            return None, 0
        
        if len(X) == 0:
            return None, 0
        
        # Ambil sample terbaru
        latest_features = X[-1].reshape(1, -1)
        latest_scaled = self.scaler.transform(latest_features)
        
        # Prediksi probabilitas
        proba = self.model.predict_proba(latest_scaled)[0]
        
        direction = 1 if np.argmax(proba) == 1 else -1
        confidence = max(proba) * 100
        
        return direction, confidence
    
    def get_prediction_summary(self):
        direction, conf = self.predict()
        if direction is None:
            return "Prediksi ML: Data tidak cukup"
        dir_text = "NAIK" if direction == 1 else "TURUN"
        return f"Prediksi ML (tuned, {self.target_days} hari): {dir_text} (conf {conf:.1f}%)"

# Fungsi utilitas untuk memuat model yang sudah ada
def get_predictor(symbol, target_days=5):
    try:
        return MLPredictorAdvanced(symbol, target_days, use_tuned=True)
    except:
        try:
            return MLPredictorAdvanced(symbol, target_days, use_tuned=False)
        except:
            return None

def get_ml_report(symbol):
    """
    Mengambil laporan performa model ML untuk saham tertentu.
    """
    report_path = os.path.join(REPORT_DIR, f"{symbol}_metrics.json")
    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            return json.load(f)
    return None