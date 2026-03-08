# scripts/dqn_environment.py
import numpy as np
import pandas as pd
import sqlite3
from scripts.agent_logger import AgentLogger

class DQNEnvironment:
    """
    Environment untuk DQN dengan state kontinu.
    State terdiri dari:
    - Regime (one-hot 4)
    - Rata-rata confidence agent (4)
    - Akurasi agent dalam 7 hari terakhir (4)
    - Volatilitas terkini (1)
    - Sentimen pasar (1) - dari berita klaster
    """
    
    def __init__(self, n_agents=4, n_regimes=4):
        self.n_agents = n_agents
        self.n_regimes = n_regimes
        self.state_size = n_regimes + n_agents + n_agents + 2  # regime + confidence + accuracy + vol + sentiment
        self.action_size = n_agents + 1  # pilih agent + weighted voting
        
        self.logger = AgentLogger()
        self.current_state = None
        self.current_regime = 0
    
    def _get_agent_confidence(self, days_back=1):
        """Ambil confidence rata-rata dari setiap agent untuk hari terakhir."""
        conn = sqlite3.connect('data/saham.db')
        query = f"""
            SELECT agent_name, AVG(confidence) as avg_conf
            FROM agent_performance
            WHERE date >= date('now', '-{days_back} days')
            GROUP BY agent_name
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        conf = np.zeros(self.n_agents)
        for _, row in df.iterrows():
            name = row['agent_name']
            if name == 'trend_xgboost':
                conf[0] = row['avg_conf']
            elif name == 'mean_reversion':
                conf[1] = row['avg_conf']
            elif name == 'breakout_lstm':
                conf[2] = row['avg_conf']
            elif name == 'gorengan':
                conf[3] = row['avg_conf']
        return conf
    
    def _get_agent_accuracy(self, days_back=7):
        """Hitung akurasi (actual_return > 0) untuk setiap agent."""
        conn = sqlite3.connect('data/saham.db')
        query = f"""
            SELECT agent_name, 
                   COUNT(*) as total,
                   SUM(CASE WHEN actual_return > 0 THEN 1 ELSE 0 END) as wins
            FROM agent_performance
            WHERE actual_return IS NOT NULL
            AND date >= date('now', '-{days_back} days')
            GROUP BY agent_name
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        acc = np.zeros(self.n_agents)
        for _, row in df.iterrows():
            name = row['agent_name']
            total = row['total']
            if total > 0:
                wins = row['wins']
                acc_val = wins / total
                if name == 'trend_xgboost':
                    acc[0] = acc_val
                elif name == 'mean_reversion':
                    acc[1] = acc_val
                elif name == 'breakout_lstm':
                    acc[2] = acc_val
                elif name == 'gorengan':
                    acc[3] = acc_val
        return acc
    
    def _get_volatility(self):
        """Ambil volatilitas IHSG atau rata-rata saham."""
        conn = sqlite3.connect('data/saham.db')
        # Coba ambil data IHSG (JKSE)
        df = pd.read_sql("SELECT Close FROM saham WHERE Symbol='JKSE' ORDER BY Date DESC LIMIT 20", conn)
        conn.close()
        
        if len(df) >= 2:
            returns = df['Close'].pct_change().dropna()
            volatility = returns.std()
        else:
            volatility = 0.02  # default 2%
        
        return min(volatility * 100, 1.0)  # scale to 0-1
    
    def _get_sentiment(self):
        """Ambil sentimen pasar dari klaster berita."""
        conn = sqlite3.connect('data/saham.db')
        df = pd.read_sql("SELECT AVG(avg_sentiment) as sentiment FROM cluster_sentiments", conn)
        conn.close()
        sentiment = df['sentiment'].iloc[0]
        if pd.isna(sentiment):
            sentiment = 0
        # convert -1..1 to 0..1
        return (sentiment + 1) / 2
    
    def get_state(self):
        """Bangun state kontinu."""
        # Regime one-hot
        regime_one_hot = np.zeros(self.n_regimes)
        if 0 <= self.current_regime < self.n_regimes:
            regime_one_hot[self.current_regime] = 1
        
        # Confidence agent
        conf = self._get_agent_confidence(days_back=1)
        
        # Accuracy agent
        acc = self._get_agent_accuracy(days_back=7)
        
        # Volatilitas
        vol = self._get_volatility()
        
        # Sentimen
        sentiment = self._get_sentiment()
        
        state = np.concatenate([regime_one_hot, conf, acc, [vol, sentiment]])
        return state.astype(np.float32)
    
    def set_regime(self, regime):
        self.current_regime = regime
    
    def get_reward(self, action, actual_return):
        """
        Hitung reward berdasarkan aksi yang diambil dan return aktual.
        action: 0-3 (pilih agent tertentu), 4 (weighted voting)
        """
        # Reward positif jika aksi sesuai dengan agent terbaik, negatif jika sebaliknya
        # Sederhana: reward = actual_return jika aksi benar, -actual_return jika salah
        # Di sini kita butuh data agent mana yang terbaik pada hari itu
        # Untuk sementara, kita asumsikan reward diambil dari data historis
        return actual_return  # akan diisi di training