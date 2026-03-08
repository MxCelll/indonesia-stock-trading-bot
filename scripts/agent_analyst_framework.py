# scripts/agent_analyst_framework.py
import numpy as np
import pandas as pd
import sqlite3
import logging
import os
import glob
import json
from datetime import datetime
from scripts.fundamental import enrich_with_fundamental, fundamental_score
from scripts.sentiment_news import get_news_sentiment
from scripts.ml_predictor_advanced import get_predictor
from scripts.cluster_tracker import get_cluster_sentiment_for_symbol
from scripts.economic_risk import get_current_risk_level
from scripts.analysts.macro_analyst import MacroAnalyst
from scripts.analysts.strategy_adapter import StrategyAdapter
from scripts.analysts.geopolitical_analyst import GeopoliticalAnalyst  # jika ada
from scripts.strategies import trend_swing_signal, gorengan_mode_signal
from scripts.agent_logger import AgentLogger
from scripts.ensemble_predictor import get_ensemble_predictor
from scripts.sentiment_news import get_numeric_sentiment

logger = logging.getLogger(__name__)

def direction_text(d):
    return "NAIK" if d == 1 else "TURUN" if d == -1 else "NETRAL"

class BaseAnalyst:
    """Base class untuk semua agent analis."""
    def analyze(self, symbol, df):
        """Mengembalikan dict dengan keys: prob_up, prob_down, confidence, reason."""
        raise NotImplementedError

class AnnouncementAnalyst(BaseAnalyst):
    """Analis fundamental."""
    def analyze(self, symbol, df):
        fundamental = enrich_with_fundamental(symbol, df)
        if not fundamental:
            return {'prob_up': 0.5, 'prob_down': 0.5, 'confidence': 0, 'reason': 'No fundamental data'}
        score, reason = fundamental_score(fundamental)
        prob_up = score / 100.0
        prob_down = 1 - prob_up
        confidence = abs(score - 50) * 2
        return {
            'prob_up': prob_up,
            'prob_down': prob_down,
            'confidence': confidence,
            'reason': f"Fundamental: {reason[:50]}"
        }

class EventAnalyst(BaseAnalyst):
    """
    Analis yang fokus pada sentimen berita dan klaster.
    Menggunakan Google News + IndoBERT.
    """
    def analyze(self, symbol, df):
        numeric_sentiment = get_numeric_sentiment(symbol, days_back=1)
        cluster_sent = get_cluster_sentiment_for_symbol(symbol)
        
        # Gabungkan (bobot: 60% berita, 40% klaster)
        news_score = (numeric_sentiment + 1) / 2
        cluster_score = (cluster_sent + 1) / 2
        combined = 0.6 * news_score + 0.4 * cluster_score
        
        prob_up = combined
        prob_down = 1 - combined
        confidence = abs(combined - 0.5) * 200
        
        return {
            'prob_up': prob_up,
            'prob_down': prob_down,
            'confidence': confidence,
            'reason': f"News: {numeric_sentiment:.2f}, Cluster: {cluster_sent:.2f}"
        }
    
    def _get_numeric_sentiment_and_text(self, symbol):
        try:
            from scripts.sentiment_news import get_news_analyzer, get_sentiment_for_period, get_news_sentiment
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            score = get_sentiment_for_period(symbol, start_date, end_date)
            text = get_news_sentiment(symbol, days_back=1)
            return score, text
        except Exception as e:
            logger.warning(f"Gagal mengambil sentimen berita untuk {symbol}: {e}")
            return 0.0, "📰 Sentimen tidak tersedia"

class PriceMomentumAnalyst(BaseAnalyst):
    """
    Analis momentum harga menggunakan ensemble XGBoost + LightGBM + LSTM.
    Prioritas: Ensemble > LSTM > XGBoost tunggal.
    """
    def analyze(self, symbol, df):
        # 1. Coba ensemble (XGBoost + LightGBM)
        try:
            from scripts.ensemble_predictor import EnsemblePredictor
            ensemble = EnsemblePredictor(symbol)
            direction, confidence = ensemble.predict()
            prob_up = confidence / 100.0 if direction == 1 else 1 - confidence / 100.0
            prob_down = 1 - prob_up
            return {
                'prob_up': prob_up,
                'prob_down': prob_down,
                'confidence': confidence,
                'reason': f"Ensemble: {direction_text(direction)} ({confidence:.1f}%)"
            }
        except Exception as e:
            logger.debug(f"Ensemble tidak tersedia untuk {symbol}: {e}")
        
        # 2. Coba LSTM
        try:
            from scripts.lstm_predictor import predict_lstm
            lstm_dir, lstm_conf, lstm_price = predict_lstm(symbol)
            if lstm_dir != 0 and lstm_conf > 50:  # Hanya gunakan jika confidence > 50%
                prob_up = lstm_conf / 100.0 if lstm_dir == 1 else 1 - lstm_conf / 100.0
                prob_down = 1 - prob_up
                return {
                    'prob_up': prob_up,
                    'prob_down': prob_down,
                    'confidence': lstm_conf,
                    'reason': f"LSTM: {direction_text(lstm_dir)} ({lstm_conf:.1f}%)"
                }
        except Exception as e:
            logger.debug(f"LSTM tidak tersedia untuk {symbol}: {e}")
        
        # 3. Fallback ke XGBoost tunggal
        from scripts.ml_predictor_advanced import get_predictor
        predictor = get_predictor(symbol)
        if predictor is None:
            return {'prob_up': 0.5, 'prob_down': 0.5, 'confidence': 0, 'reason': 'No ML model'}
        direction, confidence = predictor.predict()
        prob_up = confidence / 100.0 if direction == 1 else 1 - confidence / 100.0
        prob_down = 1 - prob_up
        return {
            'prob_up': prob_up,
            'prob_down': prob_down,
            'confidence': confidence,
            'reason': f"XGBoost: {direction_text(direction)} ({confidence:.1f}%)"
        }

class MarketAnalyst(BaseAnalyst):
    """Analis makroekonomi."""
    def analyze(self, symbol, df):
        risk = get_current_risk_level()
        if risk['risk_level'] == 'LOW':
            prob_up, prob_down, confidence = 0.6, 0.4, 60
        elif risk['risk_level'] == 'MEDIUM':
            prob_up, prob_down, confidence = 0.5, 0.5, 50
        else:
            prob_up, prob_down, confidence = 0.3, 0.7, 70
        return {
            'prob_up': prob_up,
            'prob_down': prob_down,
            'confidence': confidence,
            'reason': f"Economic risk: {risk['risk_level']} - {risk['message'][:50]}"
        }

class BestStrategyAnalyst(BaseAnalyst):
    """Analis yang menggunakan strategi terbaik hasil pencarian LLM."""
    def __init__(self, strategy_file=None):
        self.strategies = []
        if strategy_file and os.path.exists(strategy_file):
            with open(strategy_file, 'r') as f:
                self.strategies = json.load(f)
            logging.info(f"Loaded {len(self.strategies)} best strategies from {strategy_file}")
        else:
            logging.warning("No strategy file found, using default empty strategy.")
            self.strategies = []
    
    def analyze(self, symbol, df):
        if not self.strategies:
            return {
                'prob_up': 0.5,
                'prob_down': 0.5,
                'confidence': 0,
                'reason': 'No best strategy loaded'
            }
        strategy = self.strategies[0]
        entry_conditions = strategy.get('entry_conditions', [])
        exit_conditions = strategy.get('exit_conditions', [])
        
        entry_signal = conditions_to_function(entry_conditions, df)
        exit_signal = conditions_to_function(exit_conditions, df)
        
        last_entry = entry_signal.iloc[-1] if not entry_signal.empty else False
        last_exit = exit_signal.iloc[-1] if not exit_signal.empty else False
        
        if last_entry:
            prob_up = 0.7
            prob_down = 0.3
            confidence = 70
            reason = f"Entry signal from best strategy: {strategy.get('name', 'Unknown')}"
        elif last_exit:
            prob_up = 0.3
            prob_down = 0.7
            confidence = 70
            reason = f"Exit signal from best strategy: {strategy.get('name', 'Unknown')}"
        else:
            prob_up = 0.5
            prob_down = 0.5
            confidence = 0
            reason = "No signal from best strategy"
        
        return {
            'prob_up': prob_up,
            'prob_down': prob_down,
            'confidence': confidence,
            'reason': reason
        }

class MacroAnalystAgent(BaseAnalyst):
    """Agen analisis makro (IHSG, sektor, risiko)."""
    def __init__(self):
        self.macro = MacroAnalyst()
    
    def analyze(self, symbol, df):
        result = self.macro.analyze(symbol)
        score = result['score'] / 100.0
        prob_up = score
        prob_down = 1 - score
        confidence = abs(score - 0.5) * 200
        return {
            'prob_up': prob_up,
            'prob_down': prob_down,
            'confidence': confidence,
            'reason': f"Macro: {result['reasons']}"
        }

class StrategyAdapterAgent(BaseAnalyst):
    """Agen yang merekomendasikan strategi berdasarkan adaptasi."""
    def __init__(self):
        self.adapter = StrategyAdapter()
    
    def analyze(self, symbol, df):
        try:
            from scripts.regime_classifier import get_regime_classifier
            classifier = get_regime_classifier()
            regime = classifier.predict_regime(df)
            
            strategy_name, params, reason = self.adapter.get_best_strategy_for_regime(symbol, df, regime)
            
            if strategy_name == 'trend_swing':
                sig, signal_reason = trend_swing_signal(df, params)
            elif strategy_name == 'gorengan':
                sig, signal_reason = gorengan_mode_signal(df)
            else:
                sig = 0
                signal_reason = "Tidak ada sinyal"
            
            prob_up = 0.5 + (sig * 0.3)
            prob_down = 0.5 - (sig * 0.3)
            confidence = 70 if sig != 0 else 0
            
            return {
                'prob_up': prob_up,
                'prob_down': prob_down,
                'confidence': confidence,
                'reason': f"StrategyAdapter: {reason} -> {signal_reason}"
            }
        except Exception as e:
            logger.error(f"Error di StrategyAdapterAgent untuk {symbol}: {e}")
            return {
                'prob_up': 0.5,
                'prob_down': 0.5,
                'confidence': 0,
                'reason': f"StrategyAdapter error: {str(e)}"
            }

class GeopoliticalAnalyst(BaseAnalyst):
    """Analis risiko geopolitik global."""
    def __init__(self):
        from scripts.geopolitical_risk import GeopoliticalRiskAnalyzer
        self.analyzer = GeopoliticalRiskAnalyzer()

    def analyze(self, symbol, df):
        try:
            from scripts.geopolitical_risk import get_geopolitical_risk
            risk = get_geopolitical_risk()
            score = risk['score']
            level = risk['level']
            
            # Konversi skor risiko ke probabilitas naik/turun
            # Risiko tinggi -> prob turun lebih besar
            prob_up = 1 - score
            prob_down = score
            confidence = score * 100  # confidence sebesar tingkat risiko
            
            return {
                'prob_up': prob_up,
                'prob_down': prob_down,
                'confidence': confidence,
                'reason': f"Geopolitik: {level} (skor {score:.2f}) - {risk['description']}"
            }
        except Exception as e:
            logger.error(f"Error di GeopoliticalAnalyst: {e}")
            return {
                'prob_up': 0.5,
                'prob_down': 0.5,
                'confidence': 0,
                'reason': "Geopolitik: data tidak tersedia"
            }

def conditions_to_function(conditions, df):
    """Konversi daftar kondisi menjadi boolean series."""
    if not conditions:
        return pd.Series(True, index=df.index)
    
    result = pd.Series(True, index=df.index)
    for cond in conditions:
        ind = cond.get('indicator')
        op = cond.get('operator')
        val = cond.get('value')
        
        if ind is None or op is None or val is None:
            continue
        if ind not in df.columns:
            continue
        
        data = df[ind]
        
        if isinstance(val, str) and val in df.columns:
            if op == '>':
                result &= (data > df[val])
            elif op == '<':
                result &= (data < df[val])
            elif op == '>=':
                result &= (data >= df[val])
            elif op == '<=':
                result &= (data <= df[val])
            elif op == '==':
                result &= (data == df[val])
            continue
        
        try:
            num_val = float(val)
        except:
            continue
        
        if op == '>':
            result &= (data > num_val)
        elif op == '<':
            result &= (data < num_val)
        elif op == '>=':
            result &= (data >= num_val)
        elif op == '<=':
            result &= (data <= num_val)
        elif op == '==':
            result &= (data == num_val)
    
    return result

class PredictionAgent:
    """Agent yang menggabungkan output dari semua analis."""
    def __init__(self, analysts):
        self.analysts = analysts  # list of (name, analyst_obj, weight)
        self.current_regime = 'unknown'
    
    def set_regime(self, regime):
        self.current_regime = regime
    
    def predict(self, symbol, df):
        results = []
        total_weight = 0
        for name, analyst, weight in self.analysts:
            res = analyst.analyze(symbol, df)
            if res['confidence'] >= 0:  # semua agen dicatat
                signal = 1 if res['prob_up'] > res['prob_down'] else -1 if res['prob_up'] < res['prob_down'] else 0
                # Catat ke logger (actual_return akan diisi kemudian)
                AgentLogger.log_agent_decision(
                    symbol=symbol,
                    date=df.iloc[-1]['Date'].strftime('%Y-%m-%d'),
                    agent_name=name,
                    signal=signal,
                    confidence=res['confidence'],
                    regime=self.current_regime,
                    actual_return=None
                )
                results.append({
                    'name': name,
                    'prob_up': res['prob_up'],
                    'prob_down': res['prob_down'],
                    'confidence': res['confidence'],
                    'weight': weight,
                    'reason': res['reason']
                })
                total_weight += weight
        
        if not results:
            return {'prob_up': 0.5, 'prob_down': 0.5, 'confidence': 0, 'details': []}
        
        weighted_up = sum(r['prob_up'] * r['weight'] for r in results) / total_weight
        weighted_down = sum(r['prob_down'] * r['weight'] for r in results) / total_weight
        avg_confidence = sum(r['confidence'] * r['weight'] for r in results) / total_weight
        
        return {
            'prob_up': weighted_up,
            'prob_down': weighted_down,
            'confidence': avg_confidence,
            'details': results
        }

def create_default_analysts():
    """Membuat daftar analis dengan bobot default."""
    import glob, os
    strategy_file = None
    files = glob.glob('best_strategies_*.json')
    if files:
        latest_file = max(files, key=os.path.getctime)
        strategy_file = latest_file
        logging.info(f"Using best strategy file: {strategy_file}")
    
    weights = AgentLogger.get_all_agent_weights()
    default_weights = {
        'Announcement': 0.15,
        'Event': 0.10,
        'Momentum': 0.20,
        'Market': 0.10,
        'BestStrategy': 0.20,
        'Macro': 0.10,
        'StrategyAdapter': 0.10,
        'Geopolitical': 0.05  # agen baru dengan bobot kecil
    }
    for agent in default_weights:
        if agent in weights:
            default_weights[agent] = weights[agent]
    
    analysts = [
        ('Announcement', AnnouncementAnalyst(), default_weights['Announcement']),
        ('Event', EventAnalyst(), default_weights['Event']),
        ('Momentum', PriceMomentumAnalyst(), default_weights['Momentum']),
        ('Market', MarketAnalyst(), default_weights['Market']),
        ('BestStrategy', BestStrategyAnalyst(strategy_file), default_weights['BestStrategy']),
        ('Macro', MacroAnalystAgent(), default_weights['Macro']),
        ('StrategyAdapter', StrategyAdapterAgent(), default_weights['StrategyAdapter']),
        ('Geopolitical', GeopoliticalAnalyst(), default_weights['Geopolitical'])
    ]
    return analysts