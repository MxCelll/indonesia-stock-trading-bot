# scripts/sector_rotation.py
import sqlite3
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from scripts.data_utils import ambil_data_dari_db, tambah_indikator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SectorRotationAnalyzer:
    """
    Menganalisis korelasi antar saham dalam satu klaster (sektor) untuk menentukan kekuatan sektor dan leader.
    """
    
    def __init__(self, lookback_days=90):
        self.lookback_days = lookback_days
        self.conn = sqlite3.connect('data/saham.db')
        self.cursor = self.conn.cursor()
        self._ensure_table()
    
    def _ensure_table(self):
        """Buat tabel untuk menyimpan data korelasi sektor."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sector_correlation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_name TEXT,
                symbol TEXT,
                correlation_to_cluster REAL,
                is_leader INTEGER,
                rolling_correlation REAL,
                calculated_at TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sector_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_name TEXT,
                avg_return REAL,
                std_return REAL,
                sharpe_ratio REAL,
                win_rate REAL,
                total_return REAL,
                calculated_at TEXT
            )
        ''')
        self.conn.commit()
    
    def get_cluster_symbols(self, cluster_name):
        """Ambil daftar simbol dalam satu klaster dari tabel news_clusters."""
        self.cursor.execute('''
            SELECT symbols FROM news_clusters WHERE cluster_name = ?
        ''', (cluster_name,))
        row = self.cursor.fetchone()
        if row:
            return row[0].split(',')
        return []
    
    def get_all_clusters(self):
        """Ambil semua nama klaster dari tabel news_clusters."""
        self.cursor.execute('SELECT DISTINCT cluster_name FROM news_clusters')
        return [row[0] for row in self.cursor.fetchall()]
    
    def calculate_cluster_correlation(self, cluster_name):
        """
        Hitung korelasi setiap saham terhadap rata-rata klaster.
        Juga hitung performa klaster (return, volatilitas, Sharpe).
        """
        symbols = self.get_cluster_symbols(cluster_name)
        if len(symbols) < 2:
            logging.warning(f"Klaster {cluster_name} memiliki kurang dari 2 saham, lewati.")
            return None, None, None  # perbaikan: kembalikan 3 nilai
        
        # Ambil data harga untuk semua simbol
        price_data = {}
        for sym in symbols:
            df = ambil_data_dari_db(sym, hari=self.lookback_days)
            if df is None or len(df) < 30:
                continue
            df = df.set_index('Date')
            price_data[sym] = df['Close']
        
        if len(price_data) < 2:
            return None, None, None
        
        # Gabungkan menjadi DataFrame
        cluster_df = pd.DataFrame(price_data)
        cluster_df = cluster_df.dropna()
        
        # Hitung return harian
        returns = cluster_df.pct_change().dropna()
        
        # Rata-rata klaster (equal-weighted)
        cluster_avg = returns.mean(axis=1)
        
        # Hitung korelasi setiap saham terhadap rata-rata klaster
        correlations = {}
        for sym in returns.columns:
            corr = returns[sym].corr(cluster_avg)
            correlations[sym] = corr if not pd.isna(corr) else 0
        
        # Tentukan leader (saham dengan korelasi tertinggi dan return positif)
        leader_candidates = [(sym, corr) for sym, corr in correlations.items() if corr > 0.7]
        if leader_candidates:
            # Pilih dengan korelasi tertinggi
            leader = max(leader_candidates, key=lambda x: x[1])[0]
        else:
            # Jika tidak ada korelasi >0.7, ambil yang tertinggi
            leader = max(correlations, key=correlations.get) if correlations else None
        
        # Hitung rolling korelasi untuk leader (opsional)
        rolling_corr = {}
        if leader:
            # Rolling correlation 20 hari
            rolling_corr[leader] = returns[leader].rolling(20).corr(cluster_avg).iloc[-1]
        
        return correlations, leader, rolling_corr
    
    def calculate_cluster_performance(self, cluster_name):
        """
        Hitung metrik performa klaster: return rata-rata, volatilitas, Sharpe ratio.
        """
        symbols = self.get_cluster_symbols(cluster_name)
        if len(symbols) < 2:
            return None
        
        # Ambil data harga
        price_data = {}
        for sym in symbols:
            df = ambil_data_dari_db(sym, hari=self.lookback_days)
            if df is None or len(df) < 30:
                continue
            df = df.set_index('Date')
            price_data[sym] = df['Close']
        
        if len(price_data) < 2:
            return None
        
        cluster_df = pd.DataFrame(price_data)
        cluster_df = cluster_df.dropna()
        returns = cluster_df.pct_change().dropna()
        
        # Rata-rata klaster
        cluster_avg = returns.mean(axis=1)
        
        # Metrik
        avg_return = cluster_avg.mean() * 252  # annualized
        std_return = cluster_avg.std() * np.sqrt(252)
        sharpe = avg_return / std_return if std_return != 0 else 0
        win_rate = (cluster_avg > 0).mean()
        total_return = (1 + cluster_avg).prod() - 1
        
        return {
            'avg_return': avg_return,
            'std_return': std_return,
            'sharpe_ratio': sharpe,
            'win_rate': win_rate,
            'total_return': total_return
        }
    
    def update_all_clusters(self):
        """Update data korelasi dan performa untuk semua klaster."""
        clusters = self.get_all_clusters()
        for cluster in clusters:
            logging.info(f"Memproses klaster {cluster}...")
            correlations, leader, rolling_corr = self.calculate_cluster_correlation(cluster)
            if correlations is None:
                continue
            
            # Simpan korelasi per saham
            for sym, corr in correlations.items():
                self.cursor.execute('''
                    INSERT INTO sector_correlation 
                    (cluster_name, symbol, correlation_to_cluster, is_leader, rolling_correlation, calculated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    cluster,
                    sym,
                    corr,
                    1 if sym == leader else 0,
                    rolling_corr.get(sym, 0),
                    datetime.now().isoformat()
                ))
            
            # Hitung dan simpan performa klaster
            perf = self.calculate_cluster_performance(cluster)
            if perf:
                self.cursor.execute('''
                    INSERT INTO sector_performance
                    (cluster_name, avg_return, std_return, sharpe_ratio, win_rate, total_return, calculated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cluster,
                    perf['avg_return'],
                    perf['std_return'],
                    perf['sharpe_ratio'],
                    perf['win_rate'],
                    perf['total_return'],
                    datetime.now().isoformat()
                ))
            
            self.conn.commit()
        
        logging.info(f"Update selesai untuk {len(clusters)} klaster.")
    
    def get_strongest_sectors(self, top_n=3):
        """Ambil sektor dengan Sharpe ratio tertinggi."""
        self.cursor.execute('''
            SELECT cluster_name, sharpe_ratio, total_return 
            FROM sector_performance 
            ORDER BY calculated_at DESC LIMIT 50
        ''')
        rows = self.cursor.fetchall()
        if not rows:
            return []
        
        # Ambil data terbaru per cluster
        df = pd.DataFrame(rows, columns=['cluster', 'sharpe', 'return'])
        latest = df.groupby('cluster').first().reset_index()
        latest = latest.sort_values('sharpe', ascending=False).head(top_n)
        return latest.to_dict('records')
    
    def get_leader_for_sector(self, cluster_name):
        """Ambil leader untuk sektor tertentu."""
        self.cursor.execute('''
            SELECT symbol FROM sector_correlation 
            WHERE cluster_name = ? AND is_leader = 1
            ORDER BY calculated_at DESC LIMIT 1
        ''', (cluster_name,))
        row = self.cursor.fetchone()
        return row[0] if row else None

# Singleton instance
_analyzer_instance = None

def get_sector_analyzer():
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = SectorRotationAnalyzer()
    return _analyzer_instance