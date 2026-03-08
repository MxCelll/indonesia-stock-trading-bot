# scripts/news_cluster_fetcher.py
import requests
import sqlite3
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import networkx as nx
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
import os
import time

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
if not NEWS_API_KEY:
    raise ValueError("NEWS_API_KEY tidak ditemukan di file .env")

class NewsClusterFetcher:
    """
    Fetcher untuk berita dan pembangunan klaster antar saham.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        # Batas query NewsAPI: 2000 karakter
        self.max_query_length = 2000
    
    def split_symbols_into_batches(self, symbols: list, max_batch_size: int = 15) -> list:
        """
        Membagi daftar simbol menjadi batch untuk menghindari query terlalu panjang.
        """
        batches = []
        current_batch = []
        current_length = 0
        
        for sym in symbols:
            clean_sym = sym.replace('.JK', '')
            # Panjang perkiraan: panjang simbol + 2 untuk OR
            item_len = len(clean_sym) + 3  # " OR " tambahan
            if current_length + item_len > self.max_query_length:
                # Batas tercapai, simpan batch dan mulai baru
                if current_batch:
                    batches.append(current_batch)
                current_batch = [clean_sym]
                current_length = item_len
            else:
                current_batch.append(clean_sym)
                current_length += item_len
        
        if current_batch:
            batches.append(current_batch)
        
        logging.info(f"Total {len(symbols)} simbol dibagi menjadi {len(batches)} batch")
        return batches
    
    def fetch_news_batch(self, batch_symbols: list, days_back: int = 7) -> pd.DataFrame:
        """
        Mengambil berita untuk satu batch simbol.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        query = " OR ".join(batch_symbols)
        
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': query,
            'apiKey': NEWS_API_KEY,
            'language': 'id',
            'from': start_date.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d'),
            'pageSize': 100,
            'sortBy': 'publishedAt'
        }
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            if response.status_code == 401:
                logging.error("API Key tidak valid atau telah kedaluwarsa. Periksa NEWS_API_KEY di file .env")
                return pd.DataFrame()
            elif response.status_code != 200:
                logging.error(f"Gagal mengambil berita: HTTP {response.status_code}")
                return pd.DataFrame()
            
            data = response.json()
            if data['status'] != 'ok':
                logging.error(f"NewsAPI error: {data.get('message', 'Unknown')}")
                return pd.DataFrame()
            
            articles = data['articles']
            if not articles:
                return pd.DataFrame()
            
            # Deteksi saham mana yang disebut di setiap artikel
            records = []
            for article in articles:
                title = article.get('title', '')
                description = article.get('description', '') or ''
                content = title + " " + description
                
                mentioned = []
                for sym in batch_symbols:
                    if sym.lower() in content.lower():
                        mentioned.append(sym + '.JK')  # kembalikan dengan .JK
                
                if len(mentioned) >= 2:
                    records.append({
                        'date': article['publishedAt'][:10],
                        'title': title,
                        'description': description,
                        'url': article['url'],
                        'source': article['source']['name'],
                        'mentioned_symbols': ','.join(mentioned),
                        'symbol_count': len(mentioned)
                    })
            
            return pd.DataFrame(records)
            
        except requests.exceptions.Timeout:
            logging.error(f"Timeout saat mengambil berita untuk batch {batch_symbols[:3]}...")
            return pd.DataFrame()
        except Exception as e:
            logging.error(f"Error mengambil berita: {e}")
            return pd.DataFrame()
    
    def fetch_news_for_symbols(self, symbols: list, days_back: int = 7) -> pd.DataFrame:
        """
        Mengambil berita untuk daftar simbol dengan batching.
        """
        all_articles = []
        batches = self.split_symbols_into_batches(symbols)
        
        for i, batch in enumerate(batches):
            logging.info(f"Mengambil batch {i+1}/{len(batches)} ({len(batch)} simbol)...")
            df = self.fetch_news_batch(batch, days_back)
            if not df.empty:
                all_articles.append(df)
            # Jeda untuk menghindari rate limit (max 5 requests per detik)
            time.sleep(0.5)
        
        if all_articles:
            combined = pd.concat(all_articles, ignore_index=True)
            logging.info(f"Berhasil mengambil {len(combined)} artikel dengan multiple mentions")
            return combined
        else:
            logging.info("Tidak ada artikel dengan multiple mentions")
            return pd.DataFrame()
    
    def build_cooccurrence_matrix(self, articles_df: pd.DataFrame, symbols: list) -> pd.DataFrame:
        """
        Membangun co-occurrence matrix antar saham.
        """
        if articles_df.empty:
            return pd.DataFrame(0, index=symbols, columns=symbols)
        
        # Inisialisasi matrix
        n = len(symbols)
        matrix = pd.DataFrame(0, index=symbols, columns=symbols)
        
        # Hitung co-occurrence
        for _, row in articles_df.iterrows():
            mentioned = row['mentioned_symbols'].split(',')
            # Tambahkan 1 untuk setiap pasangan
            for i in range(len(mentioned)):
                for j in range(i+1, len(mentioned)):
                    matrix.loc[mentioned[i], mentioned[j]] += 1
                    matrix.loc[mentioned[j], mentioned[i]] += 1
        
        logging.info(f"Co-occurrence matrix built with {matrix.values.sum()//2} edges")
        return matrix
    
    def build_cooccurrence_graph(self, cooccurrence_matrix: pd.DataFrame, threshold: int = 1) -> nx.Graph:
        """
        Membangun graph dari co-occurrence matrix.
        Hanya edge dengan weight >= threshold yang digunakan.
        """
        G = nx.Graph()
        
        # Tambah nodes
        for symbol in cooccurrence_matrix.index:
            G.add_node(symbol)
        
        # Tambah edges
        for i, sym1 in enumerate(cooccurrence_matrix.index):
            for j, sym2 in enumerate(cooccurrence_matrix.columns):
                if i < j:  # hanya upper triangle
                    weight = cooccurrence_matrix.iloc[i, j]
                    if weight >= threshold:
                        G.add_edge(sym1, sym2, weight=weight)
        
        logging.info(f"Graph built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        return G
    
    def detect_clusters(self, G: nx.Graph, method: str = 'louvain') -> dict:
        """
        Mendeteksi klaster dalam graph menggunakan community detection.
        Method: 'louvain', 'greedy', 'label_propagation'
        """
        try:
            import community as community_louvain
            from networkx.algorithms import community
            
            if method == 'louvain':
                partition = community_louvain.best_partition(G, weight='weight')
            elif method == 'greedy':
                communities = community.greedy_modularity_communities(G, weight='weight')
                partition = {}
                for i, comm in enumerate(communities):
                    for node in comm:
                        partition[node] = i
            elif method == 'label_propagation':
                communities = community.label_propagation_communities(G)
                partition = {}
                for i, comm in enumerate(communities):
                    for node in comm:
                        partition[node] = i
            else:
                raise ValueError(f"Method {method} tidak dikenal")
            
            clusters = defaultdict(list)
            for node, cluster_id in partition.items():
                clusters[f"Cluster_{cluster_id}"].append(node)
            
            logging.info(f"Detected {len(clusters)} clusters")
            return dict(clusters)
            
        except ImportError:
            logging.error("python-louvain belum terinstall. Jalankan: pip install python-louvain networkx")
            return {}
    
    def save_to_database(self, clusters: dict, cooccurrence_matrix: pd.DataFrame, 
                         db_path: str = 'data/saham.db'):
        """
        Menyimpan hasil klaster ke database.
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_name TEXT,
                symbols TEXT,
                detected_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_cooccurrence (
                symbol1 TEXT,
                symbol2 TEXT,
                weight INTEGER,
                PRIMARY KEY (symbol1, symbol2)
            )
        ''')
        
        cursor.execute("DELETE FROM news_clusters")
        cursor.execute("DELETE FROM news_cooccurrence")
        
        for cluster_name, sym_list in clusters.items():
            cursor.execute('''
                INSERT INTO news_clusters (cluster_name, symbols, detected_at)
                VALUES (?, ?, ?)
            ''', (cluster_name, ','.join(sym_list), datetime.now().isoformat()))
        
        for i, sym1 in enumerate(cooccurrence_matrix.index):
            for j, sym2 in enumerate(cooccurrence_matrix.columns):
                if i < j:
                    weight = cooccurrence_matrix.iloc[i, j]
                    if weight > 0:
                        cursor.execute('''
                            INSERT INTO news_cooccurrence (symbol1, symbol2, weight)
                            VALUES (?, ?, ?)
                        ''', (sym1, sym2, weight))
        
        conn.commit()
        conn.close()
        logging.info(f"Data klaster disimpan ke database")
    
    def update_clusters(self, symbols: list, days_back: int = 7):
        """
        Fungsi utama untuk update klaster berita.
        """
        articles = self.fetch_news_for_symbols(symbols, days_back)
        if articles.empty:
            logging.warning("Tidak ada artikel dengan multiple mentions")
            return False
        
        co_matrix = self.build_cooccurrence_matrix(articles, symbols)
        G = self.build_cooccurrence_graph(co_matrix, threshold=1)
        clusters = self.detect_clusters(G, method='louvain')
        
        if clusters:
            self.save_to_database(clusters, co_matrix)
            return True
        return False


# Singleton instance
_fetcher_instance = None

def get_fetcher():
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = NewsClusterFetcher()
    return _fetcher_instance