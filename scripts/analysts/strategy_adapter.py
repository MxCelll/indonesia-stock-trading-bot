# scripts/analysts/strategy_adapter.py
import json
import os
import logging
from datetime import datetime, timedelta
from scripts.strategies import trend_swing_signal, gorengan_mode_signal
from scripts.regime_classifier import get_regime_classifier
from scripts.strategy_selector import load_optimal_params, load_optimal_params_per_regime

logger = logging.getLogger(__name__)

class StrategyAdapter:
    """
    Agen yang menyesuaikan parameter strategi berdasarkan rezim pasar.
    Juga memilih strategi mana yang paling cocok untuk saham ini saat ini.
    """
    def __init__(self):
        self.regime_classifier = get_regime_classifier()
        self.param_cache = {}
        self.last_update = None
    
    def get_best_strategy_for_regime(self, symbol, df, regime):
        global_params = load_optimal_params()
        params_per_regime = load_optimal_params_per_regime(symbol)
        
        if regime in params_per_regime:
            params = params_per_regime[regime]
        else:
            params = global_params.get('trend_swing', {})
        
        if regime in ['trending_bull', 'trending_bear']:
            strategy_name = 'trend_swing'
            reason = f"Pasar trending, gunakan TrendSwing"
        elif regime == 'high_volatility':
            strategy_name = 'gorengan'
            reason = f"Volatilitas tinggi, gunakan GorenganMode"
        else:
            strategy_name = 'sideways'
            reason = f"Pasar sideways, disarankan tidak trading"
        
        return strategy_name, params, reason
    
    def evaluate_strategy_performance(self, symbol, days=30):
        """
        Evaluasi performa strategi dalam periode terakhir.
        Bisa digunakan untuk menyesuaikan bobot.
        """
        # Implementasi bisa menggunakan data dari trade_journal
        # Untuk sederhana, kita return score default
        return 0.5