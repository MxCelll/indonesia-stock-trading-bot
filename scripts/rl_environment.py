# scripts/rl_environment.py
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from scripts.agent_logger import AgentLogger

class TradingEnv(gym.Env):
    """
    Environment trading untuk RL Agent.
    State: regime (one-hot encoded) + metrik agent terbaru
    Action: pilih agent (0-3) atau kombinasi (4)
    Reward: return yang dihasilkan oleh agent terpilih
    """
    
    def __init__(self, n_agents=4, n_regimes=4, lookback_days=30):
        super().__init__()
        
        self.n_agents = n_agents
        self.n_regimes = n_regimes
        self.lookback_days = lookback_days
        
        # Action space: 0-3 (pilih agent tertentu), 4 (weighted voting)
        self.action_space = spaces.Discrete(n_agents + 1)
        
        # Observation space: [regime_one_hot(4) + avg_confidence(1) + recent_accuracy(1)]
        self.observation_space = spaces.Box(
            low=0, high=1, shape=(n_regimes + 2,), dtype=np.float32
        )
        
        self.logger = AgentLogger()
        self.current_step = 0
        self.data = []
    
    def _get_obs(self):
        """Bangun observasi dari data terkini."""
        # One-hot encoding regime
        regime_one_hot = np.zeros(self.n_regimes)
        if 0 <= self.current_regime < self.n_regimes:
            regime_one_hot[self.current_regime] = 1
        
        # Hitung rata-rata confidence dari semua agent dalam 7 hari terakhir
        confidences = []
        for agent_id in range(self.n_agents):
            agent_name = self._agent_id_to_name(agent_id)
            perf = self.logger.get_agent_performance(agent_name, days_back=7)
            if perf:
                confidences.extend([p[1] for p in perf])
        
        avg_confidence = np.mean(confidences) if confidences else 0.5
        
        # Hitung akurasi recent (berdasarkan actual_return > 0)
        correct = 0
        total = 0
        for agent_id in range(self.n_agents):
            agent_name = self._agent_id_to_name(agent_id)
            perf = self.logger.get_agent_performance(agent_name, days_back=self.lookback_days)
            for _, _, ret in perf:
                if ret is not None:
                    total += 1
                    if ret > 0:
                        correct += 1
        
        recent_accuracy = correct / total if total > 0 else 0.5
        
        return np.concatenate([regime_one_hot, [avg_confidence, recent_accuracy]]).astype(np.float32)
    
    def _agent_id_to_name(self, agent_id):
        """Mapping agent ID ke nama."""
        names = ['trend_xgboost', 'mean_reversion', 'breakout_lstm', 'gorengan']
        return names[agent_id] if agent_id < len(names) else 'unknown'
    
    def step(self, action):
        """
        Jalankan aksi dan hitung reward.
        action: 0-3 (pilih agent tertentu), 4 (weighted voting)
        """
        # Simulasikan pengambilan keputusan (akan diimplementasi di luar)
        # Di sini kita hanya menghitung reward berdasarkan data historis
        # Untuk sederhananya, kita ambil performa agent pada hari yang sama
        
        # Cari data historis untuk hari ini (simulasi)
        if self.current_step < len(self.data):
            actual_return = self.data[self.current_step]['actual_return']
            best_agent = self.data[self.current_step]['best_agent']
            
            if action == best_agent or (action == 4 and best_agent in range(4)):
                reward = actual_return if actual_return > 0 else -abs(actual_return) * 0.5
            else:
                reward = -abs(actual_return) if actual_return < 0 else -actual_return * 0.5
        else:
            reward = 0
        
        self.current_step += 1
        terminated = self.current_step >= len(self.data)
        truncated = False
        
        return self._get_obs(), reward, terminated, truncated, {}
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.current_regime = 0  # default
        return self._get_obs(), {}
    
    def set_regime(self, regime):
        """Set regime saat ini (dari GMM classifier)."""
        self.current_regime = regime
    
    def load_historical_data(self, data):
        """
        Muat data historis untuk training.
        data: list of dict dengan keys 'date', 'actual_return', 'best_agent'
        """
        self.data = data