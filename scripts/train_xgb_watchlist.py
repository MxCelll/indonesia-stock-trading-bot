# train_xgb_watchlist.py
from scripts.ml_train_advanced import train_advanced_model
from scripts.watchlist import load_watchlist

watchlist = load_watchlist()
symbols = [s for s in watchlist['symbols'] if s != 'BBCA.JK'][:5]  # 5 saham selain BBCA

for symbol in symbols:
    print(f"Training XGBoost untuk {symbol}...")
    try:
        train_advanced_model(symbol, target_days=5, tune=False)
    except Exception as e:
        print(f"Gagal: {e}")