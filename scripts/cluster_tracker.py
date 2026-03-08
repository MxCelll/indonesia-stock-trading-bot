# scripts/cluster_tracker.py
import sqlite3
import pandas as pd
import logging
from datetime import datetime
from scripts.sentiment_analyzer import get_analyzer
from collections import defaultdict

logger = logging.getLogger(__name__)
logger.info("cluster_tracker.py: mulai")

class ClusterTracker:
    """
    Pelacak sentimen klaster dan integrasi ke bot.
    """

    def __init__(self):
        self.analyzer = get_analyzer(use_finbert=False)  # gunakan VADER karena PyTorch bermasalah

    def get_latest_clusters(self, db_path: str = 'data/saham.db') -> list:
        """
        Mengambil klaster terbaru dari database.
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT cluster_name, symbols, detected_at FROM news_clusters
            ORDER BY detected_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()

        clusters = []
        for row in rows:
            clusters.append({
                'name': row[0],
                'symbols': row[1].split(','),
                'detected_at': row[2]
            })
        return clusters

    def get_cooccurrence_for_symbol(self, symbol: str, db_path: str = 'data/saham.db') -> list:
        """
        Mengambil saham-saham yang sering muncul bersama dengan symbol.
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT symbol2, weight FROM news_cooccurrence
            WHERE symbol1 = ? ORDER BY weight DESC LIMIT 10
        ''', (symbol,))
        rows = cursor.fetchall()
        conn.close()

        return [{'symbol': r[0], 'weight': r[1]} for r in rows]

    def update_cluster_sentiments(self) -> dict:
        """
        Update sentimen untuk semua klaster yang ada.
        """
        clusters = self.get_latest_clusters()
        results = {}

        for cluster in clusters:
            # Ambil sentimen untuk klaster ini
            sent = self.analyzer.get_cluster_sentiment(cluster['symbols'])
            results[cluster['name']] = sent

        # Simpan ke database
        self._save_sentiments(results)
        return results

    def _save_sentiments(self, sentiments: dict, db_path: str = 'data/saham.db'):
        """
        Menyimpan hasil sentimen klaster ke database.
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cluster_sentiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_name TEXT,
                symbols TEXT,
                avg_sentiment REAL,
                positive_ratio REAL,
                negative_ratio REAL,
                article_count INTEGER,
                sentiment TEXT,
                updated_at TEXT
            )
        ''')

        for name, data in sentiments.items():
            cursor.execute('''
                INSERT INTO cluster_sentiments 
                (cluster_name, symbols, avg_sentiment, positive_ratio, negative_ratio, 
                 article_count, sentiment, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                data['cluster'],
                data['avg_sentiment'],
                data['positive_ratio'],
                data['negative_ratio'],
                data['article_count'],
                data['sentiment'],
                datetime.now().isoformat()
            ))

        conn.commit()
        conn.close()
        logging.info(f"Sentimen {len(sentiments)} klaster disimpan")

    def get_strongest_sentiment_clusters(self, sentiment_type: str = 'positive',
                                         min_articles: int = 5) -> list:
        """
        Mengambil klaster dengan sentimen terkuat.
        """
        conn = sqlite3.connect('data/saham.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM cluster_sentiments
            WHERE sentiment = ? AND article_count >= ?
            ORDER BY avg_sentiment DESC
            LIMIT 10
        ''', (sentiment_type, min_articles))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_cluster_recommendations(self) -> dict:
        """
        Memberikan rekomendasi berdasarkan sentimen klaster.
        """
        positive = self.get_strongest_sentiment_clusters('positive', min_articles=3)
        negative = self.get_strongest_sentiment_clusters('negative', min_articles=3)

        return {
            'buy_candidates': [{'cluster': r[1], 'symbols': r[2], 'score': r[3]} for r in positive],
            'sell_candidates': [{'cluster': r[1], 'symbols': r[2], 'score': r[3]} for r in negative]
        }


def get_cluster_sentiment_for_symbol(symbol: str, db_path: str = 'data/saham.db') -> float:
    """
    Mengambil skor sentimen klaster untuk suatu saham.
    Mengembalikan nilai antara -1 (negatif) hingga 1 (positif), atau 0 jika tidak ada data.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Cari klaster yang mengandung symbol
    cursor.execute('''
        SELECT cluster_name FROM news_clusters 
        WHERE symbols LIKE ?
    ''', (f'%{symbol}%',))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return 0.0

    cluster_name = row[0]

    # Ambil sentimen terbaru untuk klaster tersebut
    cursor.execute('''
        SELECT avg_sentiment FROM cluster_sentiments
        WHERE cluster_name = ?
        ORDER BY updated_at DESC LIMIT 1
    ''', (cluster_name,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return float(row[0])
    else:
        return 0.0


# Singleton instance
_tracker_instance = None

def get_tracker():
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = ClusterTracker()
    return _tracker_instance