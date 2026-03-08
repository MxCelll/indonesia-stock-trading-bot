# scripts/train_dqn.py
import numpy as np
import pandas as pd
import sqlite3
import logging
from scripts.dqn_agent import DQNAgent
from scripts.dqn_environment import DQNEnvironment
from scripts.agent_logger import AgentLogger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def prepare_training_data(days_back=90):
    """
    Ambil data dari agent_performance dan siapkan untuk training DQN.
    Returns: list of tuples (state, action, reward, next_state, done)
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
        return []
    
    # Mapping agent name ke ID
    agent_map = {
        'trend_xgboost': 0,
        'mean_reversion': 1,
        'breakout_lstm': 2,
        'gorengan': 3
    }
    
    # Kelompokkan per hari
    experiences = []
    env = DQNEnvironment()
    
    for date, group in df.groupby('date'):
        # Tentukan agent terbaik hari itu (dengan return tertinggi)
        best_agent = group.loc[group['actual_return'].idxmax()]
        best_agent_id = agent_map.get(best_agent['agent_name'], 0)
        
        # Regime
        regime = int(best_agent['regime']) if pd.notna(best_agent['regime']) else 0
        env.set_regime(regime)
        
        # State saat ini
        state = env.get_state()
        
        # Aksi terbaik adalah memilih agent terbaik
        action = best_agent_id
        
        # Reward = actual_return dari agent terbaik (normalized)
        reward = best_agent['actual_return'] / 100  # skala -0.1..0.15
        
        # Next state (sederhana, asumsikan sama untuk demo)
        # Dalam praktik, perlu data hari berikutnya
        next_state = state  # placeholder
        
        done = False
        experiences.append((state, action, reward, next_state, done))
    
    return experiences

def train_dqn(episodes=100, days_back=90):
    """
    Latih DQN agent menggunakan data historis.
    """
    logging.info("Menyiapkan data training...")
    experiences = prepare_training_data(days_back)
    if not experiences:
        logging.warning("Tidak cukup data untuk training.")
        return
    
    # Inisialisasi environment dan agent
    env = DQNEnvironment()
    agent = DQNAgent(state_size=env.state_size, action_size=env.action_size)
    
    # Training loop
    for episode in range(episodes):
        total_reward = 0
        for exp in experiences:
            state, action, reward, next_state, done = exp
            agent.remember(state, action, reward, next_state, done)
            agent.replay()
            total_reward += reward
        
        if (episode+1) % 10 == 0:
            logging.info(f"Episode {episode+1}/{episodes}, Total Reward: {total_reward:.2f}, Epsilon: {agent.epsilon:.3f}")
    
    # Simpan model
    agent.save()
    logging.info("Training selesai. Model disimpan.")

if __name__ == "__main__":
    train_dqn(episodes=50, days_back=90)