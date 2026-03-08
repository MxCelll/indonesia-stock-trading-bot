# scripts/lstm_predictor.py
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import joblib
import os
import logging
import itertools
import json
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from scripts.data_utils import ambil_data_dari_db, tambah_indikator

logger = logging.getLogger(__name__)
MODEL_DIR = 'data/lstm_models'
os.makedirs(MODEL_DIR, exist_ok=True)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
logger.info(f"LSTM predictor using device: {device}")

class LSTMPredictor(nn.Module):
    """
    LSTM untuk prediksi harga saham.
    """
    def __init__(self, input_dim=50, hidden_dim=128, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True, dropout=dropout)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim, 1)  # Output regresi harga
    
    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.dropout(out[:, -1, :])  # Ambil output timestep terakhir
        out = self.fc(out)
        return out

def create_sequences(data, seq_length=60, target_col='Close', pred_days=5):
    """
    Membuat sequence untuk training LSTM.
    target_col: kolom yang diprediksi (Close)
    pred_days: jumlah hari ke depan yang diprediksi
    """
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(data)
    
    X, y = [], []
    for i in range(len(scaled_data) - seq_length - pred_days + 1):
        X.append(scaled_data[i:i+seq_length])
        # Target: harga di hari ke i+seq_length+pred_days-1
        target_idx = data.columns.get_loc(target_col)
        y.append(scaled_data[i+seq_length+pred_days-1, target_idx])
    
    return np.array(X), np.array(y), scaler

def train_lstm(symbol, seq_length=60, epochs=100, batch_size=32, lookback_days=1000):
    """
    Melatih model LSTM untuk satu saham dengan parameter default.
    """
    logger.info(f"Training LSTM untuk {symbol}...")
    
    df = ambil_data_dari_db(symbol, hari=lookback_days)
    if df is None or len(df) < 500:
        raise ValueError(f"Data tidak cukup untuk {symbol}")
    
    df = tambah_indikator(df)
    
    feature_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'MACD', 'MACD_diff', 'EMA20', 'EMA50', 'ATR', 'ADX']
    feature_cols = [col for col in feature_cols if col in df.columns]
    
    data = df[feature_cols].copy()
    X, y, scaler = create_sequences(data, seq_length, target_col='Close', pred_days=5)
    
    # Train-test split
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    # Convert to tensor
    X_train_t = torch.tensor(X_train, dtype=torch.float32).to(device)
    y_train_t = torch.tensor(y_train, dtype=torch.float32).view(-1, 1).to(device)
    X_test_t = torch.tensor(X_test, dtype=torch.float32).to(device)
    y_test_t = torch.tensor(y_test, dtype=torch.float32).view(-1, 1).to(device)
    
    # DataLoader
    train_dataset = TensorDataset(X_train_t, y_train_t)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    
    # Model dengan parameter default
    hidden_dim = 128
    num_layers = 2
    dropout = 0.2
    model = LSTMPredictor(input_dim=len(feature_cols), hidden_dim=hidden_dim, num_layers=num_layers, dropout=dropout).to(device)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # Training loop
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch+1) % 20 == 0:
            logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(train_loader):.6f}")
    
    # Evaluasi
    model.eval()
    with torch.no_grad():
        train_pred = model(X_train_t)
        test_pred = model(X_test_t)
        train_loss = criterion(train_pred, y_train_t).item()
        test_loss = criterion(test_pred, y_test_t).item()
    
    logger.info(f"Train MSE: {train_loss:.6f}, Test MSE: {test_loss:.6f}")
    
    # Simpan model, scaler, dan arsitektur
    torch.save(model.state_dict(), os.path.join(MODEL_DIR, f"{symbol}_lstm.pth"))
    joblib.dump(scaler, os.path.join(MODEL_DIR, f"{symbol}_scaler.pkl"))
    with open(os.path.join(MODEL_DIR, f"{symbol}_features.txt"), 'w') as f:
        f.write('\n'.join(feature_cols))
    # Simpan arsitektur
    arch = {
        'input_dim': len(feature_cols),
        'hidden_dim': hidden_dim,
        'num_layers': num_layers,
        'dropout': dropout
    }
    with open(os.path.join(MODEL_DIR, f"{symbol}_arch.json"), 'w') as f:
        json.dump(arch, f)
    
    logger.info(f"Model LSTM default untuk {symbol} disimpan.")
    return model, scaler

def tune_lstm(symbol, seq_lengths=[30, 60, 90], hidden_dims=[64, 128, 256], 
              num_layers_list=[1, 2, 3], learning_rates=[0.001, 0.01], 
              dropout_list=[0.2, 0.5], epochs=30, cv_folds=3):
    """
    Melakukan hyperparameter tuning untuk LSTM menggunakan grid search sederhana.
    """
    logger.info(f"Tuning LSTM untuk {symbol}...")
    
    # Ambil data
    df = ambil_data_dari_db(symbol, hari=1000)
    if df is None or len(df) < 500:
        raise ValueError(f"Data tidak cukup untuk {symbol}")
    
    df = tambah_indikator(df)
    feature_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'MACD', 'MACD_diff', 'EMA20', 'EMA50', 'ATR', 'ADX']
    feature_cols = [col for col in feature_cols if col in df.columns]
    data = df[feature_cols].copy()
    
    best_params = {}
    best_loss = float('inf')
    results = []
    
    # Grid search
    for seq_len, hidden_dim, num_layers, lr, dropout in itertools.product(
        seq_lengths, hidden_dims, num_layers_list, learning_rates, dropout_list):
        
        logger.info(f"Testing seq_len={seq_len}, hidden={hidden_dim}, layers={num_layers}, lr={lr}, dropout={dropout}")
        
        try:
            # Buat sequences
            X, y, scaler = create_sequences(data, seq_len, target_col='Close', pred_days=5)
            
            # Train-test split time-based
            split = int(len(X) * 0.8)
            X_train, X_test = X[:split], X[split:]
            y_train, y_test = y[:split], y[split:]
            
            X_train_t = torch.tensor(X_train, dtype=torch.float32).to(device)
            y_train_t = torch.tensor(y_train, dtype=torch.float32).view(-1, 1).to(device)
            X_test_t = torch.tensor(X_test, dtype=torch.float32).to(device)
            y_test_t = torch.tensor(y_test, dtype=torch.float32).view(-1, 1).to(device)
            
            model = LSTMPredictor(input_dim=len(feature_cols), hidden_dim=hidden_dim, 
                                   num_layers=num_layers, dropout=dropout).to(device)
            criterion = nn.MSELoss()
            optimizer = optim.Adam(model.parameters(), lr=lr)
            
            # Training
            model.train()
            for epoch in range(epochs):
                optimizer.zero_grad()
                outputs = model(X_train_t)
                loss = criterion(outputs, y_train_t)
                loss.backward()
                optimizer.step()
            
            # Evaluasi
            model.eval()
            with torch.no_grad():
                test_pred = model(X_test_t)
                test_loss = criterion(test_pred, y_test_t).item()
            
            logger.info(f"Test loss: {test_loss:.6f}")
            
            results.append({
                'seq_length': seq_len,
                'hidden_dim': hidden_dim,
                'num_layers': num_layers,
                'learning_rate': lr,
                'dropout': dropout,
                'test_loss': test_loss
            })
            
            if test_loss < best_loss:
                best_loss = test_loss
                best_params = {
                    'seq_length': seq_len,
                    'hidden_dim': hidden_dim,
                    'num_layers': num_layers,
                    'learning_rate': lr,
                    'dropout': dropout
                }
        except Exception as e:
            logger.error(f"Error pada kombinasi {seq_len},{hidden_dim},{num_layers},{lr},{dropout}: {e}")
            continue
    
    # Simpan hasil tuning
    results_path = os.path.join(MODEL_DIR, f"{symbol}_tuning_results.json")
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Best params untuk {symbol}: {best_params}")
    return best_params, results

def load_lstm(symbol):
    """
    Memuat model LSTM yang sudah dilatih beserta arsitektur dan scaler.
    """
    model_path = os.path.join(MODEL_DIR, f"{symbol}_lstm.pth")
    scaler_path = os.path.join(MODEL_DIR, f"{symbol}_scaler.pkl")
    feat_path = os.path.join(MODEL_DIR, f"{symbol}_features.txt")
    arch_path = os.path.join(MODEL_DIR, f"{symbol}_arch.json")
    
    if not os.path.exists(model_path) or not os.path.exists(arch_path):
        return None, None, None
    
    with open(feat_path, 'r') as f:
        feature_cols = [line.strip() for line in f.readlines()]
    
    with open(arch_path, 'r') as f:
        arch = json.load(f)
    
    model = LSTMPredictor(
        input_dim=arch['input_dim'],
        hidden_dim=arch['hidden_dim'],
        num_layers=arch['num_layers'],
        dropout=arch['dropout']
    ).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    
    scaler = joblib.load(scaler_path)
    return model, scaler, feature_cols

def train_lstm_with_best_params(symbol, epochs=100):
    """
    Melatih LSTM dengan parameter terbaik hasil tuning.
    Jika belum ada hasil tuning, gunakan default.
    """
    results_path = os.path.join(MODEL_DIR, f"{symbol}_tuning_results.json")
    if os.path.exists(results_path):
        with open(results_path, 'r') as f:
            results = json.load(f)
        best = min(results, key=lambda x: x['test_loss'])
        seq_len = best['seq_length']
        hidden_dim = best['hidden_dim']
        num_layers = best['num_layers']
        lr = best['learning_rate']
        dropout = best['dropout']
        logger.info(f"Memuat parameter terbaik untuk {symbol}: {best}")
    else:
        # Default
        seq_len = 60
        hidden_dim = 128
        num_layers = 2
        lr = 0.001
        dropout = 0.2
        logger.info(f"Hasil tuning tidak ditemukan, gunakan default untuk {symbol}")
    
    # Training dengan parameter terbaik
    df = ambil_data_dari_db(symbol, hari=1000)
    if df is None or len(df) < 500:
        raise ValueError(f"Data tidak cukup untuk {symbol}")
    
    df = tambah_indikator(df)
    feature_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'MACD', 'MACD_diff', 'EMA20', 'EMA50', 'ATR', 'ADX']
    feature_cols = [col for col in feature_cols if col in df.columns]
    data = df[feature_cols].copy()
    X, y, scaler = create_sequences(data, seq_len, target_col='Close', pred_days=5)
    
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    X_train_t = torch.tensor(X_train, dtype=torch.float32).to(device)
    y_train_t = torch.tensor(y_train, dtype=torch.float32).view(-1, 1).to(device)
    X_test_t = torch.tensor(X_test, dtype=torch.float32).to(device)
    y_test_t = torch.tensor(y_test, dtype=torch.float32).view(-1, 1).to(device)
    
    train_dataset = TensorDataset(X_train_t, y_train_t)
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    
    model = LSTMPredictor(input_dim=len(feature_cols), hidden_dim=hidden_dim, 
                           num_layers=num_layers, dropout=dropout).to(device)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch+1) % 20 == 0:
            logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(train_loader):.6f}")
    
    model.eval()
    with torch.no_grad():
        train_pred = model(X_train_t)
        test_pred = model(X_test_t)
        train_loss = criterion(train_pred, y_train_t).item()
        test_loss = criterion(test_pred, y_test_t).item()
    
    logger.info(f"Train MSE: {train_loss:.6f}, Test MSE: {test_loss:.6f}")
    
    # Simpan model, scaler, dan arsitektur
    torch.save(model.state_dict(), os.path.join(MODEL_DIR, f"{symbol}_lstm.pth"))
    joblib.dump(scaler, os.path.join(MODEL_DIR, f"{symbol}_scaler.pkl"))
    with open(os.path.join(MODEL_DIR, f"{symbol}_features.txt"), 'w') as f:
        f.write('\n'.join(feature_cols))
    # Simpan arsitektur
    arch = {
        'input_dim': len(feature_cols),
        'hidden_dim': hidden_dim,
        'num_layers': num_layers,
        'dropout': dropout
    }
    with open(os.path.join(MODEL_DIR, f"{symbol}_arch.json"), 'w') as f:
        json.dump(arch, f)
    
    logger.info(f"Model LSTM dengan tuning untuk {symbol} disimpan.")
    return model, scaler

def predict_lstm(symbol, seq_length=60):
    """
    Menghasilkan prediksi untuk kondisi terkini.
    Returns: direction (1 naik, -1 turun), confidence (0-100), predicted_price
    """
    model, scaler, feature_cols = load_lstm(symbol)
    if model is None:
        return 0, 0, None
    
    # Ambil data terbaru
    df = ambil_data_dari_db(symbol, hari=seq_length+10)
    if df is None or len(df) < seq_length:
        return 0, 0, None
    
    df = tambah_indikator(df)
    data = df[feature_cols].tail(seq_length).copy()
    
    # Normalisasi
    scaled_data = scaler.transform(data)
    
    # Buat sequence
    X = torch.tensor(scaled_data, dtype=torch.float32).unsqueeze(0).to(device)
    
    # Prediksi
    with torch.no_grad():
        pred_scaled = model(X).item()
    
    # Inverse transform
    dummy = np.zeros((1, len(feature_cols)))
    dummy[0, feature_cols.index('Close')] = pred_scaled
    pred_price = scaler.inverse_transform(dummy)[0, feature_cols.index('Close')]
    
    current_price = df.iloc[-1]['Close']
    price_change = (pred_price - current_price) / current_price * 100
    
    if price_change > 1:
        direction = 1
        confidence = min(100, abs(price_change) * 10)
    elif price_change < -1:
        direction = -1
        confidence = min(100, abs(price_change) * 10)
    else:
        direction = 0
        confidence = 0
    
    return direction, confidence, pred_price