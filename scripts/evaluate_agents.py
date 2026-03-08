# scripts/evaluate_agents.py
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
DB_PATH = 'data/saham.db'

def evaluate_agent_performance(days_back=30):
    """
    Mengevaluasi performa semua agen dalam periode days_back terakhir.
    Menghitung akurasi, precision, recall, f1-score untuk setiap agen.
    """
    conn = sqlite3.connect(DB_PATH)
    
    query = f"""
    SELECT agent_name, signal, confidence, actual_return, regime
    FROM agent_performance
    WHERE actual_return IS NOT NULL
    AND date >= date('now', '-{days_back} days')
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        logger.warning("Tidak ada data performa dalam periode ini.")
        return None
    
    results = {}
    for agent in df['agent_name'].unique():
        df_agent = df[df['agent_name'] == agent]
        total = len(df_agent)
        
        df_agent['correct'] = ((df_agent['signal'] == 1) & (df_agent['actual_return'] > 0)) | \
                              ((df_agent['signal'] == -1) & (df_agent['actual_return'] < 0))
        
        accuracy = df_agent['correct'].mean()
        
        tp = len(df_agent[(df_agent['signal'] == 1) & (df_agent['actual_return'] > 0)])
        fp = len(df_agent[(df_agent['signal'] == 1) & (df_agent['actual_return'] <= 0)])
        fn = len(df_agent[(df_agent['signal'] != 1) & (df_agent['actual_return'] > 0)])
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        results[agent] = {
            'total_decisions': total,
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'avg_confidence': df_agent['confidence'].mean(),
            'avg_return': df_agent['actual_return'].mean()
        }
    
    return results

def print_evaluation_results(results):
    """Menampilkan hasil evaluasi dalam format teks."""
    if not results:
        return "Tidak ada data evaluasi."
    
    lines = []
    lines.append("📊 *EVALUASI PERFORMANCE AGEN (30 HARI TERAKHIR)*\n")
    for agent, metrics in results.items():
        lines.append(f"*{agent}*")
        lines.append(f"  Total keputusan: {metrics['total_decisions']}")
        lines.append(f"  Akurasi: {metrics['accuracy']:.2%}")
        lines.append(f"  Precision: {metrics['precision']:.2%}")
        lines.append(f"  Recall: {metrics['recall']:.2%}")
        lines.append(f"  F1-score: {metrics['f1']:.2f}")
        lines.append(f"  Rata-rata confidence: {metrics['avg_confidence']:.1f}%")
        lines.append(f"  Rata-rata return: {metrics['avg_return']:.2f}%\n")
    
    return '\n'.join(lines)

def update_weights_from_performance(results, learning_rate=0.1):
    """
    Memperbarui bobot agen di database berdasarkan performa.
    """
    from scripts.agent_logger import AgentLogger
    
    current_weights = AgentLogger.get_all_agent_weights()
    default_weights = {
        'Announcement': 0.15,
        'Event': 0.10,
        'Momentum': 0.20,
        'Market': 0.10,
        'BestStrategy': 0.20,
        'Macro': 0.10,
        'StrategyAdapter': 0.15,
        'Geopolitical': 0.10  # tambahkan jika ada
    }
    
    new_weights = {}
    for agent in default_weights:
        if agent in results:
            acc = results[agent]['accuracy']
            old_weight = current_weights.get(agent, default_weights[agent])
            new_weight = old_weight * (1 + learning_rate * (acc - 0.5))
            new_weights[agent] = max(0.05, min(0.5, new_weight))
        else:
            new_weights[agent] = current_weights.get(agent, default_weights[agent])
    
    total = sum(new_weights.values())
    for agent in new_weights:
        new_weights[agent] /= total
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for agent, weight in new_weights.items():
        cursor.execute('''
            INSERT OR REPLACE INTO agent_weights (agent_name, weight, updated_at)
            VALUES (?, ?, ?)
        ''', (agent, weight, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    logger.info(f"Bobot agen diperbarui: {new_weights}")
    return new_weights