# scripts/ml_train_advanced.py
import numpy as np
import pandas as pd
import joblib
import os
import json
import logging
from scripts.ml_features_advanced import create_features_advanced
from scripts.ml_tuning import tune_xgboost
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
MODEL_DIR = 'data/ml_models'
REPORT_DIR = 'data/ml_reports'
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

def save_metrics(symbol, target_days, metrics):
    """Menyimpan metrik evaluasi model ke file JSON."""
    report_path = os.path.join(REPORT_DIR, f"{symbol}_metrics.json")
    with open(report_path, 'w') as f:
        json.dump(metrics, f, indent=2)

def train_advanced_model(symbol, target_days=5, tune=True, n_iter=30):
    """
    Melatih model dengan fitur lanjutan, dengan opsi tuning.
    """
    if tune:
        # Gunakan tuning
        result = tune_xgboost(symbol, target_days, n_iter=n_iter)
        save_metrics(symbol, target_days, result)
        return result
    else:
        # Training biasa dengan fitur lanjutan tapi tanpa tuning (pakai default)
        X, y, _, feature_names, dates = create_features_advanced(symbol, lookback=30, target_days=target_days)
        
        # Train-test split time-based
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=7,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )
        
        model.fit(X_train_scaled, y_train)
        
        y_pred = model.predict(X_test_scaled)
        acc = accuracy_score(y_test, y_pred)
        logging.info(f"Test accuracy: {acc:.4f}")
        logging.info(classification_report(y_test, y_pred))
        
        # Simpan model dan scaler
        model_path = os.path.join(MODEL_DIR, f"{symbol}_xgb_adv_{target_days}d.pkl")
        scaler_path = os.path.join(MODEL_DIR, f"{symbol}_scaler_adv_{target_days}d.pkl")
        joblib.dump(model, model_path)
        joblib.dump(scaler, scaler_path)
        
        result = {
            'accuracy': acc,
            'model_path': model_path,
            'feature_names': feature_names
        }
        save_metrics(symbol, target_days, result)
        return result

def train_all_advanced(use_watchlist=True, tune=True):
    """Melatih model untuk semua saham di watchlist."""
    from scripts.watchlist import load_watchlist
    from scripts.data_utils import get_all_symbols
    
    if use_watchlist:
        watchlist = load_watchlist()
        symbols = watchlist['symbols']
    else:
        symbols = get_all_symbols()
    
    results = {}
    for symbol in symbols:
        logging.info(f"Training model advanced untuk {symbol}...")
        try:
            result = train_advanced_model(symbol, target_days=5, tune=tune, n_iter=20)
            results[symbol] = result
            logging.info(f"✅ {symbol} selesai")
        except Exception as e:
            logging.error(f"❌ {symbol} gagal: {e}")
    
    return results

if __name__ == "__main__":
    train_all_advanced(use_watchlist=True, tune=True)