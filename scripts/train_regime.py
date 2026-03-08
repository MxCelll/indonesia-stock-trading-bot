# scripts/train_regime.py
import logging
from scripts.regime_classifier import train_regime_classifier
from scripts.data_utils import get_all_symbols

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    logging.info("Memulai training regime classifier...")
    symbols = get_all_symbols()
    classifier = train_regime_classifier(symbols)
    logging.info("Training selesai.")