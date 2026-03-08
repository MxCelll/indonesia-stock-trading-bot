# scripts/ensemble_train.py
import lightgbm as lgb
import xgboost as xgb
import joblib
import os
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from scripts.ml_features_advanced import create_features_advanced

def train_ensemble(symbol, target_days=5, lookback=30, tune=False):
    # Ambil fitur
    X, y, _, feature_names, dates = create_features_advanced(symbol, lookback=lookback, target_days=target_days)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    # Latih XGBoost
    xgb_model = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42)
    xgb_model.fit(X_train, y_train)
    
    # Latih LightGBM
    lgb_model = lgb.LGBMClassifier(n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42)
    lgb_model.fit(X_train, y_train)
    
    # Simpan model
    model_dir = 'data/ml_models'
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(xgb_model, os.path.join(model_dir, f"{symbol}_xgb_ensemble.pkl"))
    joblib.dump(lgb_model, os.path.join(model_dir, f"{symbol}_lgb_ensemble.pkl"))
    
    # Evaluasi
    xgb_pred = xgb_model.predict(X_test)
    lgb_pred = lgb_model.predict(X_test)
    ensemble_pred = np.round((xgb_pred + lgb_pred) / 2).astype(int)
    acc = accuracy_score(y_test, ensemble_pred)
    print(f"Ensemble accuracy: {acc:.4f}")
    
    return [xgb_model, lgb_model], acc, X_test, y_test