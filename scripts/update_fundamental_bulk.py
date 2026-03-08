# scripts/update_fundamental_bulk.py
import sys
import os
# Tambahkan path folder utama agar Python bisa menemukan scripts
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import time
import random
import logging
from scripts.data_utils import get_all_symbols
from scripts.fundamental import fetch_and_save_fundamental

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_all_fundamental(delay=2):
    symbols = get_all_symbols()
    total = len(symbols)
    success = 0
    for i, sym in enumerate(symbols, 1):
        logger.info(f"({i}/{total}) Memproses {sym}...")
        if fetch_and_save_fundamental(sym):
            success += 1
        else:
            logger.warning(f"Gagal memperbarui {sym}")
        if i < total:
            time.sleep(random.uniform(delay, delay+1))
    logger.info(f"Selesai: {success}/{total} saham berhasil diperbarui.")

if __name__ == "__main__":
    update_all_fundamental(delay=2)