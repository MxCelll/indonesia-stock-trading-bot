# scripts/create_dummy_agent_data.py
import sqlite3
import random
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def create_dummy_data():
    """
    Mengisi tabel agent_performance dengan data dummy untuk keperluan testing RL.
    """
    conn = sqlite3.connect('data/saham.db')
    cursor = conn.cursor()
    
    # Hapus data lama jika ada
    cursor.execute("DELETE FROM agent_performance")
    
    # Daftar simbol dan agent
    symbols = ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK', 'GGRM.JK', 'ERTX.JK', 'OPMS.JK']
    agent_names = ['trend_xgboost', 'mean_reversion', 'breakout_lstm', 'gorengan']
    regimes = [0, 1, 2, 3]  # trending_bull, trending_bear, sideways, high_volatility
    
    start_date = datetime.now() - timedelta(days=100)
    
    # Buat 500 record dummy
    for i in range(500):
        symbol = random.choice(symbols)
        date = (start_date + timedelta(days=random.randint(0, 90))).strftime('%Y-%m-%d')
        agent = random.choice(agent_names)
        signal = random.choice([-1, 0, 1])
        confidence = random.uniform(0, 100)
        # Actual return antara -10% sampai +15%
        actual_return = random.uniform(-10, 15)
        regime = random.choice(regimes)
        
        cursor.execute('''
            INSERT INTO agent_performance 
            (symbol, date, agent_name, signal, confidence, actual_return, regime)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, date, agent, signal, confidence, actual_return, regime))
    
    conn.commit()
    conn.close()
    logger.info("✅ Data dummy berhasil dibuat. Total 500 record.")

if __name__ == "__main__":
    create_dummy_data()