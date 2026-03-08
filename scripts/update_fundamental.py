# scripts/update_fundamental.py
import sys
import os

# Tambahkan folder utama ke path agar modul 'scripts' dapat ditemukan
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import logging
from scripts.fundamental_fetcher import get_fetcher
from scripts.data_utils import get_all_symbols

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def update_all_fundamental():
    symbols = get_all_symbols()
    logging.info(f"Memulai update untuk {len(symbols)} saham...")
    fetcher = get_fetcher()
    results = fetcher.update_all_symbols(symbols)
    logging.info(f"Update selesai: {len(results)}/{len(symbols)} berhasil")
    return results

if __name__ == "__main__":
    update_all_fundamental()