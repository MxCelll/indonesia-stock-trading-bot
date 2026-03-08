# scripts/ml_train.py
import numpy as np
import pandas as pd
import joblib
import os
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import logging
from scripts.ml_features import create_features
from scripts.data_utils import ambil_data_dari_db, tambah_indikator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MODEL_DIR = 'data/ml_models'
os.makedirs(MODEL_DIR, exist_ok=True)

def train_xgboost(symbol, target_days=5, lookback=30, test_size=0.2):
    """
    Melatih model XGBoost untuk prediksi arah harga.
    Menggunakan TimeSeriesSplit untuk validasi [citation:3][citation:6].
    """
    logger.info(f"Training XGBoost untuk {symbol}, target={target_days} hari")
    
    # 1. Ambil data
    df = ambil_data_dari_db(symbol, hari=1000)
    if df is None or len(df) < 500:
        raise ValueError(f"Data tidak cukup untuk {symbol}")
    
    df = tambah_indikator(df)
    
    # 2. Buat fitur
    X, y, _, feature_names, indices = create_features(df, lookback, target_days)
    
    # 3. Train-test split (time-based)
    split_idx = int(len(X) * (1 - test_size))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    # 4. Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 5. Train XGBoost dengan hyperparameter default dulu [citation:2]
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    # 6. Fit model
    model.fit(X_train_scaled, y_train)
    
    # 7. Evaluasi
    y_pred = model.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    
    logger.info(f"Hasil evaluasi - Accuracy: {accuracy:.4f}, Precision: {precision:.4f}")
    logger.info(f"Recall: {recall:.4f}, F1: {f1:.4f}")
    
    # 8. Simpan model dan scaler
    model_path = os.path.join(MODEL_DIR, f"{symbol}_xgb_{target_days}d.pkl")
    scaler_path = os.path.join(MODEL_DIR, f"{symbol}_scaler_{target_days}d.pkl")
    feature_path = os.path.join(MODEL_DIR, f"{symbol}_features_{target_days}d.txt")
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    with open(feature_path, 'w') as f:
        f.write('\n'.join(feature_names))
    
    logger.info(f"Model disimpan di {model_path}")
    
    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'model_path': model_path
    }

def train_xgboost_with_cv(symbol, target_days=5, lookback=30, n_splits=5):
    """
    Training dengan time series cross-validation untuk evaluasi lebih robust [citation:3][citation:6].
    """
    logger.info(f"Training XGBoost dengan CV untuk {symbol}")
    
    df = ambil_data_dari_db(symbol, hari=1000)
    if df is None or len(df) < 500:
        raise ValueError(f"Data tidak cukup untuk {symbol}")
    
    df = tambah_indikator(df)
    X, y, _, feature_names, indices = create_features(df, lookback, target_days)
    
    # TimeSeriesSplit [citation:6]
    tscv = TimeSeriesSplit(n_splits=n_splits)
    
    cv_scores = []
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )
        
        model.fit(X_train_scaled, y_train)
        y_pred = model.predict(X_test_scaled)
        acc = accuracy_score(y_test, y_pred)
        cv_scores.append(acc)
        logger.info(f"Fold {fold+1}: Accuracy = {acc:.4f}")
    
    logger.info(f"CV Accuracy: mean={np.mean(cv_scores):.4f}, std={np.std(cv_scores):.4f}")
    
    # Train final model on all data
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    final_model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    final_model.fit(X_scaled, y)
    
    # Simpan
    model_path = os.path.join(MODEL_DIR, f"{symbol}_xgb_{target_days}d_cv.pkl")
    scaler_path = os.path.join(MODEL_DIR, f"{symbol}_scaler_{target_days}d_cv.pkl")
    joblib.dump(final_model, model_path)
    joblib.dump(scaler, scaler_path)
    
    return {
        'cv_mean': np.mean(cv_scores),
        'cv_std': np.std(cv_scores),
        'model_path': model_path
    }

if __name__ == "__main__":
    # Test untuk BBCA
    result = train_xgboost('BBCA.JK', target_days=5)
    logger.info(result)