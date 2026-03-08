# scripts/multi_agent_selector.py
import numpy as np
import pandas as pd
import sqlite3
import logging
from scripts.agent_analyst_framework import create_default_analysts, PredictionAgent
from scripts.rl_agent import get_rl_orchestrator
from scripts.agent_logger import AgentLogger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MultiAgentSystem:
    """
    Sistem multi-agent dengan online learning untuk bobot agent.
    """
    
    def __init__(self):
        # Inisialisasi analyst agents dengan bobot default
        analysts = create_default_analysts()
        self.analysts = analysts  # list of (name, analyst_obj, weight)
        self.prediction_agent = PredictionAgent(analysts)
        self.rl_orchestrator = get_rl_orchestrator()
        self.logger = AgentLogger()
        self.current_regime = 'unknown'
        self.regime_map = {
            'trending_bull': 0,
            'trending_bear': 1,
            'sideways': 2,
            'high_volatility': 3,
            'unknown': 0
        }
        self.learning_rate = 0.1  # learning rate untuk update bobot
        self.recent_trade_id = None  # akan diisi oleh trade_executor
    
    def update_regime(self, regime):
        self.current_regime = regime
    
    def update_weights(self, trade_result):
        """
        Update bobot agent berdasarkan hasil trade.
        trade_result: dict dengan keys 'agent_name', 'signal', 'confidence', 'actual_return'
        """
        for name, agent, weight in self.analysts:
            if name == trade_result['agent_name']:
                # Reward = actual_return * sign(signal)  (positif jika benar arah)
                reward = trade_result['actual_return'] * trade_result['signal']
                # Update bobot dengan rumus sederhana: weight_new = weight_old * (1 + lr * reward)
                # Normalisasi agar total bobot tetap 1
                new_weight = weight * (1 + self.learning_rate * reward / 100)
                self.analysts[self.analysts.index((name, agent, weight))] = (name, agent, new_weight)
                break
        
        # Normalisasi semua bobot
        total = sum(w for _, _, w in self.analysts)
        self.analysts = [(n, a, w/total) for n, a, w in self.analysts]
        logging.info(f"Bobot agent setelah update: {[(n, round(w,3)) for n, _, w in self.analysts]}")
    
    def get_decision_signal(self, symbol, df):
        pred = self.prediction_agent.predict(symbol, df)
        
        # Logging untuk online learning
        for detail in pred['details']:
            self.logger.log_agent_decision(
                symbol=symbol,
                date=df.iloc[-1]['Date'].strftime('%Y-%m-%d'),
                agent_name=detail['name'],
                signal=1 if detail['prob_up'] > detail['prob_down'] else -1,
                confidence=detail['confidence'],
                regime=self.current_regime,
                actual_return=None
            )
        
        regime_int = self.regime_map.get(self.current_regime, 0)
        action = self.rl_orchestrator.choose_action(regime_int)
        
        if action < len(pred['details']):
            chosen = pred['details'][action]
            final_prob_up = chosen['prob_up']
            confidence = chosen['confidence']
        else:
            final_prob_up = pred['prob_up']
            confidence = pred['confidence']
        
        if final_prob_up > 0.6:
            signal = 1
            conf = final_prob_up * 100
        elif final_prob_up < 0.4:
            signal = -1
            conf = (1 - final_prob_up) * 100
        else:
            signal = 0
            conf = 50
        
        return signal, conf, pred['details']
    
    def get_consensus_signal(self, symbol, df):
        return self.get_decision_signal(symbol, df)


# Singleton instance
_multi_agent_instance = None

def get_multi_agent():
    global _multi_agent_instance
    if _multi_agent_instance is None:
        _multi_agent_instance = MultiAgentSystem()
    return _multi_agent_instance