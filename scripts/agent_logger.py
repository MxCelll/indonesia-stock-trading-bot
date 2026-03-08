# scripts/agent_logger.py
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

class AgentLogger:
    """
    Mencatat setiap keputusan agent dan hasilnya untuk digunakan RL.
    """
    
    @staticmethod
    def log_agent_decision(symbol, date, agent_name, signal, confidence, regime, actual_return=None):
        """
        Mencatat keputusan agent ke database.
        actual_return bisa diisi kemudian (setelah exit).
        """
        conn = sqlite3.connect('data/saham.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO agent_performance 
            (symbol, date, agent_name, signal, confidence, actual_return, regime)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, date, agent_name, signal, confidence, actual_return, regime))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def update_actual_return(symbol, entry_date, exit_date, actual_return):
        """
        Update actual_return untuk trade yang sudah ditutup.
        """
        conn = sqlite3.connect('data/saham.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE agent_performance 
            SET actual_return = ? 
            WHERE symbol = ? AND date = ? AND actual_return IS NULL
        ''', (actual_return, symbol, entry_date))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_agent_performance(agent_name, regime=None, days_back=90):
        """
        Mengambil performa historis agent untuk training RL.
        """
        conn = sqlite3.connect('data/saham.db')
        cursor = conn.cursor()
        
        if regime:
            cursor.execute('''
                SELECT signal, confidence, actual_return FROM agent_performance
                WHERE agent_name = ? AND regime = ? AND actual_return IS NOT NULL
                AND date >= date('now', ?)
            ''', (agent_name, regime, f'-{days_back} days'))
        else:
            cursor.execute('''
                SELECT signal, confidence, actual_return FROM agent_performance
                WHERE agent_name = ? AND actual_return IS NOT NULL
                AND date >= date('now', ?)
            ''', (agent_name, f'-{days_back} days'))
        
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    @staticmethod
    def calculate_accuracy(agent_name, regime=None, days_back=30):
        """
        Menghitung akurasi agent (berapa kali sinyal benar).
        """
        rows = AgentLogger.get_agent_performance(agent_name, regime, days_back)
        if not rows:
            return 0.5  # default jika tidak ada data
        correct = 0
        total = 0
        for signal, conf, ret in rows:
            if ret is not None:
                total += 1
                # Jika return positif dan sinyal beli (1) atau return negatif dan sinyal jual (-1), dianggap benar
                if (ret > 0 and signal == 1) or (ret < 0 and signal == -1):
                    correct += 1
        return correct / total if total > 0 else 0.5
    
    @staticmethod
    def get_all_agent_weights():
        """
        Mengambil bobot terakhir dari database.
        """
        conn = sqlite3.connect('data/saham.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_weights (
                agent_name TEXT PRIMARY KEY,
                weight REAL,
                updated_at TEXT
            )
        ''')
        cursor.execute('SELECT agent_name, weight FROM agent_weights')
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}
    
    @staticmethod
    def update_weights(learning_rate=0.1, days_back=30):
        """
        Menghitung ulang bobot agent berdasarkan akurasi 30 hari terakhir.
        """
        # Daftar agent yang ada (sesuai dengan framework)
        agent_names = ['Announcement', 'Event', 'Momentum', 'Market', 'BestStrategy']
        regimes = [0,1,2,3]  # trending_bull, trending_bear, sideways, high_volatility
        conn = sqlite3.connect('data/saham.db')
        cursor = conn.cursor()
        
        # Hitung akurasi per agent
        accuracies = {}
        for agent in agent_names:
            acc = AgentLogger.calculate_accuracy(agent, days_back=days_back)
            accuracies[agent] = acc
        
        # Normalisasi bobot (agar total = 1)
        total_acc = sum(accuracies.values())
        if total_acc > 0:
            new_weights = {agent: acc / total_acc for agent, acc in accuracies.items()}
        else:
            # Jika semua 0.5, gunakan bobot default
            new_weights = {agent: 1/len(agent_names) for agent in agent_names}
        
        # Simpan ke database
        for agent, weight in new_weights.items():
            cursor.execute('''
                INSERT OR REPLACE INTO agent_weights (agent_name, weight, updated_at)
                VALUES (?, ?, ?)
            ''', (agent, weight, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return new_weights