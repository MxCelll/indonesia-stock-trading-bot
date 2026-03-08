# scripts/rl_agent.py
import numpy as np
import sqlite3
import pandas as pd
from collections import defaultdict
import joblib
import os

class RLOrchestrator:
    """
    Reinforcement Learning Agent untuk memilih atau menggabungkan sinyal dari multi-agent.
    Menggunakan Q-Learning dengan state: regime + metrik pasar.
    """
    
class RLOrchestrator:
    def __init__(self, n_agents=7, n_regimes=4, learning_rate=0.1, discount_factor=0.95, epsilon=0.1):
        self.n_agents = n_agents
        self.n_regimes = n_regimes
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.q_table = np.zeros((n_regimes, n_agents + 1))
        self.performance_history = {i: [] for i in range(n_agents)}
        self.meta_lr = 0.05
        
        self.model_path = 'data/rl_orchestrator.pkl'
        if os.path.exists(self.model_path):
            self.load()
    
    def update_meta_weights(self):
        """
        Meta-learning: perbarui bobot berdasarkan performa 14 hari terakhir.
        Agen yang performanya baik akan dinaikkan bobotnya.
        """
        for agent_id in range(self.n_agents):
            perf = self.performance_history[agent_id][-14:]
            if len(perf) > 0:
                avg_perf = np.mean(perf)
                # Update Q-table dengan meta-lr
                for regime in range(self.n_regimes):
                    self.q_table[regime][agent_id] += self.meta_lr * avg_perf
        self.normalize_q_table()
    
    def normalize_q_table(self):
        """Normalisasi agar setiap baris jumlahnya 1 (opsional)."""
        for regime in range(self.n_regimes):
            total = np.sum(self.q_table[regime])
            if total > 0:
                self.q_table[regime] /= total
    
    def log_performance(self, agent_id, performance):
        """Mencatat performa agent untuk meta-learning."""
        self.performance_history[agent_id].append(performance)
        if len(self.performance_history[agent_id]) > 30:
            self.performance_history[agent_id].pop(0)
    
    def choose_action(self, regime, use_epsilon=True):
        """
        Pilih aksi berdasarkan Q-table.
        Aksi: 0-3 (pilih agent tertentu), 4 (weighted voting)
        """
        if use_epsilon and np.random.random() < self.epsilon:
            return np.random.randint(self.n_agents + 1)
        else:
            return np.argmax(self.q_table[regime])
    
    def update(self, regime, action, reward, next_regime):
        """
        Update Q-table menggunakan rumus Q-learning.
        """
        best_next_action = np.argmax(self.q_table[next_regime])
        td_target = reward + self.gamma * self.q_table[next_regime][best_next_action]
        td_error = td_target - self.q_table[regime][action]
        self.q_table[regime][action] += self.lr * td_error
    
    def train_from_history(self, df):
        """
        Latih Q-table dari data historis.
        df harus memiliki kolom: regime, action, reward, next_regime
        """
        for _, row in df.iterrows():
            self.update(
                int(row['regime']),
                int(row['action']),
                row['reward'],
                int(row['next_regime'])
            )
        self.save()
    
    def get_best_agent(self, regime):
        """Kembalikan aksi terbaik untuk regime tertentu."""
        return np.argmax(self.q_table[regime])
    
    def save(self):
        joblib.dump(self.q_table, self.model_path)
    
    def load(self):
        self.q_table = joblib.load(self.model_path)
    
    @staticmethod
    def prepare_training_data(days_back=90):
        """
        Ambil data dari agent_performance dan siapkan untuk training.
        """
        conn = sqlite3.connect('data/saham.db')
        query = f"""
            SELECT date, symbol, agent_name, signal, confidence, actual_return, regime
            FROM agent_performance
            WHERE actual_return IS NOT NULL
            AND date >= date('now', '-{days_back} days')
            ORDER BY date
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        if df.empty:
            return None
        
        # Mapping agent name ke ID
        agent_map = {
            'trend_xgboost': 0,
            'mean_reversion': 1,
            'breakout_lstm': 2,
            'gorengan': 3
        }
        
        # Tentukan aksi terbaik untuk setiap hari
        training_data = []
        for date, group in df.groupby('date'):
            # Asumsikan agent dengan return tertinggi adalah yang terbaik
            best_agent = group.loc[group['actual_return'].idxmax()]
            best_agent_id = agent_map.get(best_agent['agent_name'], 0)
            
            # Regime saat ini
            regime = int(best_agent['regime']) if pd.notna(best_agent['regime']) else 0
            
            # Untuk training, kita butuh next_regime (sederhana: sama)
            # Dalam implementasi nyata, ini bisa diambil dari data berikutnya
            next_regime = regime
            
            # Reward = actual_return dari agent terbaik
            reward = best_agent['actual_return'] / 100  # skala -1..1
            
            training_data.append({
                'date': date,
                'regime': regime,
                'action': best_agent_id,
                'reward': reward,
                'next_regime': next_regime
            })
        
        return pd.DataFrame(training_data)


# Singleton instance
_rl_agent_instance = None

def get_rl_orchestrator():
    global _rl_agent_instance
    if _rl_agent_instance is None:
        _rl_agent_instance = RLOrchestrator()
    return _rl_agent_instance