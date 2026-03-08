# scripts/update_clusters.py
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import logging
from scripts.news_cluster_fetcher import get_fetcher
from scripts.cluster_tracker import get_tracker
from scripts.data_utils import get_all_symbols

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def update_all_clusters():
    """
    Update klaster berita untuk semua saham di database.
    """
    symbols = get_all_symbols()
    logging.info(f"Memulai update klaster untuk {len(symbols)} saham...")
    
    fetcher = get_fetcher()
    success = fetcher.update_clusters(symbols, days_back=30)
    
    if success:
        # Update sentimen untuk klaster yang baru
        tracker = get_tracker()
        sentiments = tracker.update_cluster_sentiments()
        logging.info(f"Sentimen untuk {len(sentiments)} klaster diupdate")
        return True
    else:
        logging.warning("Tidak ada klaster baru terdeteksi")
        return False

if __name__ == "__main__":
    update_all_clusters()