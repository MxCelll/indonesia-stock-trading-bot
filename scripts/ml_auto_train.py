# scripts/ml_auto_train.py
import logging
from scripts.data_utils import get_all_symbols
from scripts.watchlist import load_watchlist
from scripts.ml_train import train_xgboost

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def train_all_models(use_watchlist=True):
    """
    Melatih model untuk semua saham di watchlist.
    """
    if use_watchlist:
        watchlist = load_watchlist()
        symbols = watchlist['symbols']
    else:
        symbols = get_all_symbols()
    
    results = {}
    for symbol in symbols:
        logging.info(f"Training model untuk {symbol}...")
        try:
            result = train_xgboost(symbol, target_days=5)
            results[symbol] = result
            logging.info(f"✅ {symbol} selesai, accuracy={result['accuracy']:.4f}")
        except Exception as e:
            logging.error(f"❌ {symbol} gagal: {e}")
    
    return results

if __name__ == "__main__":
    train_all_models()