# scripts/ml_tuning.py
import numpy as np
import pandas as pd
import joblib
import os
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV, RandomizedSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import logging
from scripts.ml_features_advanced import create_features_advanced

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
MODEL_DIR = 'data/ml_models'

def tune_xgboost(symbol, target_days=5, n_iter=50, cv_folds=3):
    """
    Melakukan hyperparameter tuning untuk XGBoost menggunakan RandomizedSearchCV.
    """
    logger.info(f"Tuning XGBoost untuk {symbol}, target={target_days} hari")
    
    # Buat fitur
    X, y, _, feature_names, dates = create_features_advanced(symbol, lookback=30, target_days=target_days)
    
    # TimeSeriesSplit
    tscv = TimeSeriesSplit(n_splits=cv_folds)
    
    # Parameter grid untuk tuning
    param_dist = {
        'n_estimators': [50, 100, 200, 300],
        'max_depth': [3, 5, 7, 9, 12],
        'learning_rate': [0.01, 0.05, 0.1, 0.2, 0.3],
        'subsample': [0.6, 0.7, 0.8, 0.9, 1.0],
        'colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0],
        'gamma': [0, 0.1, 0.2, 0.3, 0.4],
        'reg_alpha': [0, 0.1, 0.5, 1.0],
        'reg_lambda': [0.1, 0.5, 1.0, 2.0],
        'min_child_weight': [1, 3, 5, 7]
    }
    
    # Model dasar
    xgb_model = xgb.XGBClassifier(
        objective='binary:logistic',
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    # RandomizedSearchCV
    random_search = RandomizedSearchCV(
        estimator=xgb_model,
        param_distributions=param_dist,
        n_iter=n_iter,
        cv=tscv,
        scoring='accuracy',
        verbose=1,
        random_state=42,
        n_jobs=-1
    )
    
    # Scale features (penting untuk beberapa model, XGBoost tidak terlalu sensitif tapi tetap)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Fit
    random_search.fit(X_scaled, y)
    
    # Hasil terbaik
    best_params = random_search.best_params_
    best_score = random_search.best_score_
    logger.info(f"Best parameters: {best_params}")
    logger.info(f"Best CV accuracy: {best_score:.4f}")
    
    # Evaluasi dengan confusion matrix di seluruh data (untuk referensi)
    best_model = random_search.best_estimator_
    y_pred = best_model.predict(X_scaled)
    acc = accuracy_score(y, y_pred)
    cm = confusion_matrix(y, y_pred)
    logger.info(f"Training accuracy: {acc:.4f}")
    logger.info(f"Confusion matrix:\n{cm}")
    
    # Simpan model dan scaler
    model_path = os.path.join(MODEL_DIR, f"{symbol}_xgb_tuned_{target_days}d.pkl")
    scaler_path = os.path.join(MODEL_DIR, f"{symbol}_scaler_tuned_{target_days}d.pkl")
    feature_path = os.path.join(MODEL_DIR, f"{symbol}_features_{target_days}d.txt")
    
    joblib.dump(best_model, model_path)
    joblib.dump(scaler, scaler_path)
    with open(feature_path, 'w') as f:
        f.write('\n'.join(feature_names))
    
    logger.info(f"Model tuned disimpan di {model_path}")
    
    return {
        'best_params': best_params,
        'best_cv_score': best_score,
        'accuracy': acc,
        'model_path': model_path,
        'scaler_path': scaler_path,
        'feature_names': feature_names
    }

def tune_with_grid(symbol, target_days=5):
    """
    GridSearchCV untuk tuning yang lebih exhaustive (tapi lambat).
    """
    # Parameter grid lebih kecil untuk efisiensi
    param_grid = {
        'n_estimators': [100, 200],
        'max_depth': [5, 7],
        'learning_rate': [0.05, 0.1],
        'subsample': [0.8, 0.9],
        'colsample_bytree': [0.8, 0.9]
    }
    
    X, y, _, feature_names, dates = create_features_advanced(symbol, lookback=30, target_days=target_days)
    tscv = TimeSeriesSplit(n_splits=3)
    
    xgb_model = xgb.XGBClassifier(
        objective='binary:logistic',
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    grid_search = GridSearchCV(
        estimator=xgb_model,
        param_grid=param_grid,
        cv=tscv,
        scoring='accuracy',
        verbose=1,
        n_jobs=-1
    )
    
    grid_search.fit(X_scaled, y)
    
    best_params = grid_search.best_params_
    best_score = grid_search.best_score_
    logger.info(f"GridSearch best parameters: {best_params}")
    logger.info(f"Best CV accuracy: {best_score:.4f}")
    
    model_path = os.path.join(MODEL_DIR, f"{symbol}_xgb_grid_{target_days}d.pkl")
    scaler_path = os.path.join(MODEL_DIR, f"{symbol}_scaler_grid_{target_days}d.pkl")
    joblib.dump(grid_search.best_estimator_, model_path)
    joblib.dump(scaler, scaler_path)
    
    return {
        'best_params': best_params,
        'best_cv_score': best_score,
        'model_path': model_path
    }

if __name__ == "__main__":
    # Test untuk BBCA
    result = tune_xgboost('OPMS.JK', target_days=5, n_iter=20)
    logger.info(result)