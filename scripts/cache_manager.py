# scripts/cache_manager.py
import json
import os
import time
import numpy as np

CACHE_DIR = 'data/cache'
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def numpy_encoder(obj):
    """Encoder khusus untuk menangani tipe numpy agar bisa disimpan ke JSON."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def get_cache(key, max_age_seconds=300):
    """Mengambil data dari cache berdasarkan key dengan batas umur."""
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            if time.time() - data.get('timestamp', 0) < max_age_seconds:
                return data.get('result')
        except Exception as e:
            print(f"Error membaca cache: {e}")
    return None

def set_cache(key, result):
    """Menyimpan data ke cache."""
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    data = {
        'timestamp': time.time(),
        'result': result
    }
    try:
        with open(cache_file, 'w') as f:
            json.dump(data, f, default=numpy_encoder)
    except Exception as e:
        print(f"Error menyimpan cache: {e}")

# ========== Fungsi cache khusus untuk prediksi ==========
def save_prediction_cache(symbol, direction, confidence, ttl_hours=24):
    """Simpan hasil prediksi ke cache dengan timestamp."""
    cache_file = os.path.join(CACHE_DIR, f"{symbol}_pred.json")
    data = {
        'symbol': symbol,
        'direction': direction,
        'confidence': confidence,
        'timestamp': time.time(),
        'expiry': time.time() + ttl_hours * 3600
    }
    with open(cache_file, 'w') as f:
        json.dump(data, f)

def load_prediction_cache(symbol):
    """Muat hasil prediksi dari cache jika masih berlaku."""
    cache_file = os.path.join(CACHE_DIR, f"{symbol}_pred.json")
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, 'r') as f:
            data = json.load(f)
        if time.time() < data['expiry']:
            return data['direction'], data['confidence']
        else:
            os.remove(cache_file)  # hapus jika kadaluarsa
            return None
    except:
        return None