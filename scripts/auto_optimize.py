import numpy as np
import json
import os
from scripts.walk_forward import optimize_parameters
from scripts.regime_classifier import get_regime_classifier
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
import logging

logger = logging.getLogger(__name__)

def optimize_per_regime(symbol, param_grid, method='random', n_random=30, metric='profit_factor', cv_folds=3):
    """
    Optimasi parameter untuk setiap regime pasar secara terpisah.
    Mengembalikan dict: {regime_name: best_params}
    """
    classifier = get_regime_classifier()
    if not classifier.is_trained:
        logger.error("Regime classifier belum dilatih. Jalankan train_regime.py dulu.")
        return {}

    # Ambil data historis
    df = ambil_data_dari_db(symbol, hari=1200)
    if df is None or len(df) < 500:
        logger.error(f"Data tidak cukup untuk {symbol}")
        return {}
    df = tambah_indikator(df)

    # Ekstrak fitur untuk regime
    features = classifier.extract_features(df)
    if features.empty:
        logger.error("Fitur regime tidak bisa diekstrak")
        return {}

    # Align index
    common_index = df.index.intersection(features.index)
    if len(common_index) < 500:
        logger.error("Terlalu sedikit data setelah alignment")
        return {}

    df_aligned = df.loc[common_index]
    features_aligned = features.loc[common_index]

    # Prediksi regime
    regimes_int = classifier.gmm.predict(features_aligned.values)

    # Mapping sementara (sesuaikan dengan hasil training GMM Anda)
    regime_names = {
        0: 'trending_bull',
        1: 'trending_bear',
        2: 'sideways',
        3: 'high_volatility'
    }

    results = {}
    for regime_int in np.unique(regimes_int):
        regime_name = regime_names.get(regime_int, f"regime_{regime_int}")
        regime_mask = (regimes_int == regime_int)
        df_regime = df_aligned[regime_mask].copy()
        if len(df_regime) < 200:
            logger.warning(f"Data untuk regime {regime_name} hanya {len(df_regime)} hari, lewati")
            continue

        try:
            # Jalankan optimasi pada data regime ini
            result = optimize_parameters(
                symbol=None,
                param_grid=param_grid,
                method=method,
                n_random=n_random,
                metric=metric,
                cv_folds=cv_folds,
                df=df_regime
            )
            best_params = result['best_params']
            results[regime_name] = best_params
            logger.info(f"Regime {regime_name}: best params {best_params}")
        except Exception as e:
            logger.error(f"Optimasi untuk regime {regime_name} gagal: {e}")

    return results

def save_optimal_params_per_regime(symbol, param_grid, filename='optimal_params_per_regime.json'):
    """Optimasi per regime dan simpan ke file JSON."""
    results = optimize_per_regime(symbol, param_grid)
    if not results:
        return False

    # Muat file lama jika ada
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            all_data = json.load(f)
    else:
        all_data = {}

    # Simpan per simbol
    if symbol not in all_data:
        all_data[symbol] = {}
    all_data[symbol]['trend_swing'] = results

    with open(filename, 'w') as f:
        json.dump(all_data, f, indent=2)

    logger.info(f"Parameter per regime untuk {symbol} disimpan ke {filename}")
    return True