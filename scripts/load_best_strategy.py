# scripts/load_best_strategy.py
import json
import os
import glob

def load_best_strategy(symbol=None):
    """
    Memuat strategi terbaik dari file JSON yang dihasilkan oleh analyze_strategies.
    Jika symbol diberikan, cari file dengan prefix best_strategies_*.json.
    Kembalikan dictionary strategi pertama (terbaik).
    """
    files = glob.glob("best_strategies_*.json")
    if not files:
        return None
    # Ambil file terbaru berdasarkan nama (karena ada timestamp)
    latest_file = max(files)
    with open(latest_file, 'r') as f:
        data = json.load(f)
    # data adalah list of strategies
    if not data:
        return None
    # Ambil strategi pertama (terbaik)
    best = data[0]
    return best