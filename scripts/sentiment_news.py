# scripts/sentiment_news.py
import logging
import sqlite3
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from textblob import TextBlob
from .sentiment_indobert import get_sentiment_model

logger = logging.getLogger(__name__)
DB_PATH = 'data/saham.db'

# Daftar sumber berita lokal dengan URL pencarian dan parser masing-masing
LOCAL_SOURCES = [
    {
        'name': 'Kontan',
        'url': 'https://www.kontan.co.id/search?q={query}',
        'parser': lambda soup: [
            {
                'title': a.text.strip(),
                'url': 'https://www.kontan.co.id' + a['href'],
                'date': None  # tanggal bisa diekstrak jika diperlukan
            }
            for a in soup.select('h3.title a[href]')[:10]
        ]
    },
    {
        'name': 'IDX Channel',
        'url': 'https://www.idxchannel.com/search?q={query}',
        'parser': lambda soup: [
            {
                'title': a.text.strip(),
                'url': 'https://www.idxchannel.com' + a['href'],
                'date': None
            }
            for a in soup.select('h4.title a[href]')[:10]
        ]
    },
    {
        'name': 'CNBC Indonesia',
        'url': 'https://www.cnbcindonesia.com/search?query={query}',
        'parser': lambda soup: [
            {
                'title': a.text.strip(),
                'url': a['href'],
                'date': None
            }
            for a in soup.select('a.thumb')[:10]
        ]
    },
    {
        'name': 'Bisnis.com',
        'url': 'https://search.bisnis.com/?q={query}',
        'parser': lambda soup: [
            {
                'title': a.text.strip(),
                'url': a['href'],
                'date': None
            }
            for a in soup.select('h2.title a')[:10]
        ]
    }
]

# Daftar User-Agent untuk rotasi
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
]

class NewsSentimentAnalyzer:
    def __init__(self):
        self.google_news = None  # kita tidak akan menggunakan gnews karena sering timeout, lebih baik scraping lokal
        self.indobert = get_sentiment_model()
        self.company_names = {
            'BBCA': 'Bank Central Asia',
            'BBRI': 'Bank Rakyat Indonesia',
            'BMRI': 'Bank Mandiri',
            'TLKM': 'Telkom Indonesia',
            'ASII': 'Astra International',
            'GGRM': 'Gudang Garam',
            'UNVR': 'Unilever Indonesia',
            'ANTM': 'Aneka Tambang',
            'INDF': 'Indofood Sukses Makmur',
            'ALKA': 'Alakasa Industrindo',
            'SKBM': 'Sekar Bumi',
            'ERTX': 'Eratex Djaja',
            'ESTI': 'Estika Tata Tiara',
        }
        self._init_news_cache_table()

    def _init_news_cache_table(self):
        """Membuat tabel untuk menyimpan artikel berita yang sudah diambil (cache)."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                source TEXT,
                title TEXT,
                url TEXT,
                date TEXT,
                sentiment_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_symbol ON news_cache(symbol)')
        conn.commit()
        conn.close()

    def _get_random_headers(self):
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        }

    def _fetch_url(self, url, timeout=5):
        """Mengambil konten URL dengan timeout dan rotasi User-Agent."""
        try:
            headers = self._get_random_headers()
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.warning(f"Gagal mengambil {url}: {e}")
            return None

    def scrape_source(self, source, query, timeout=5):
        """Mencoba mengambil artikel dari satu sumber."""
        try:
            url = source['url'].format(query=query.replace(' ', '+'))
            html = self._fetch_url(url, timeout)
            if not html:
                return []
            soup = BeautifulSoup(html, 'html.parser')
            articles = source['parser'](soup)
            # Tambahkan nama sumber
            for art in articles:
                art['source'] = source['name']
            return articles
        except Exception as e:
            logger.warning(f"Error scraping {source['name']}: {e}")
            return []

    def get_news_multisource(self, symbol, days_back=1):
        """
        Mengambil berita dari semua sumber lokal secara paralel.
        Mengembalikan daftar artikel unik.
        """
        clean_symbol = symbol.replace('.JK', '')
        queries = [clean_symbol]
        if clean_symbol in self.company_names:
            queries.append(self.company_names[clean_symbol])

        # Batasi tanggal (kita tidak bisa filter di sisi scraper, jadi ambil semua lalu filter nanti)
        # Untuk sementara kita ambil saja semua, karena scraper biasanya mengembalikan berita terbaru.
        all_articles = []
        with ThreadPoolExecutor(max_workers=len(LOCAL_SOURCES)) as executor:
            future_to_source = {}
            for source in LOCAL_SOURCES:
                # Coba dengan query pertama (kode saham)
                future = executor.submit(self.scrape_source, source, queries[0], timeout=5)
                future_to_source[future] = source
                # Jika ada nama perusahaan, submit juga
                if len(queries) > 1:
                    future2 = executor.submit(self.scrape_source, source, queries[1], timeout=5)
                    future_to_source[future2] = source

            for future in as_completed(future_to_source, timeout=10):
                try:
                    articles = future.result()
                    all_articles.extend(articles)
                except TimeoutError:
                    logger.warning("Timeout saat menunggu hasil scraping")
                except Exception as e:
                    logger.error(f"Error scraping: {e}")

        # Hapus duplikat berdasarkan URL
        seen = set()
        unique = []
        for art in all_articles:
            if art['url'] and art['url'] not in seen:
                seen.add(art['url'])
                unique.append(art)
        return unique

    def get_cached_news(self, symbol):
        """Mengambil berita dari cache (24 jam terakhir)."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT title, sentiment_score, source, url FROM news_cache
            WHERE symbol = ? AND created_at >= datetime('now', '-1 day')
        ''', (symbol,))
        rows = cursor.fetchall()
        conn.close()
        articles = []
        for row in rows:
            articles.append({
                'title': row[0],
                'sentiment': row[1],
                'source': row[2],
                'url': row[3]
            })
        return articles

    def save_news_to_cache(self, symbol, articles_with_sentiment):
        """Menyimpan artikel dengan skor sentimen ke cache."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for art in articles_with_sentiment:
            cursor.execute('''
                INSERT INTO news_cache (symbol, source, title, url, sentiment_score)
                VALUES (?, ?, ?, ?, ?)
            ''', (symbol, art['source'], art['title'], art['url'], art['sentiment']))
        conn.commit()
        conn.close()

    def analyze_sentiment(self, text):
        """Analisis sentimen dengan IndoBERT jika ada, fallback TextBlob."""
        if self.indobert and self.indobert.model is not None:
            try:
                return self.indobert.predict_sentiment(text)
            except Exception as e:
                logger.warning(f"IndoBERT error, fallback ke TextBlob: {e}")
        blob = TextBlob(text)
        return blob.sentiment.polarity

    def get_sentiment_score(self, symbol, days_back=1, use_cache=True):
        """
        Menghitung skor sentimen rata-rata untuk simbol tertentu.
        Menggunakan cache jika tersedia, jika tidak, melakukan scraping.
        """
        if use_cache:
            cached = self.get_cached_news(symbol)
            if cached:
                sentiments = [a['sentiment'] for a in cached]
                avg = sum(sentiments) / len(sentiments)
                logger.info(f"Sentimen dari cache untuk {symbol}: {avg:.2f} dari {len(cached)} artikel")
                return avg, len(cached)

        articles = self.get_news_multisource(symbol, days_back)
        if not articles:
            return 0.0, 0

        # Hitung sentimen untuk setiap artikel
        articles_with_sent = []
        for art in articles:
            title = art.get('title', '')
            score = self.analyze_sentiment(title)
            articles_with_sent.append({
                'title': title,
                'source': art.get('source', 'unknown'),
                'url': art.get('url', ''),
                'sentiment': score
            })

        avg_score = sum(a['sentiment'] for a in articles_with_sent) / len(articles_with_sent)
        self.save_news_to_cache(symbol, articles_with_sent)
        logger.info(f"Sentimen baru untuk {symbol}: {avg_score:.2f} dari {len(articles_with_sent)} artikel")
        return avg_score, len(articles_with_sent)

    def get_summary(self, symbol, days_back=1):
        """Mengembalikan ringkasan sentimen dalam format teks."""
        score, count = self.get_sentiment_score(symbol, days_back)
        if count == 0:
            return "📰 Tidak ada berita terkait dalam 24 jam terakhir."
        sentiment_label = "positif" if score > 0.1 else "negatif" if score < -0.1 else "netral"
        return f"📊 *Sentimen Berita* ({count} artikel)\nSkor rata-rata: {score:.2f} ({sentiment_label})"

# Singleton instance
_news_analyzer = None

def get_news_analyzer():
    global _news_analyzer
    if _news_analyzer is None:
        _news_analyzer = NewsSentimentAnalyzer()
    return _news_analyzer

def get_news_sentiment(symbol, days_back=1):
    """Untuk ditampilkan di agent (ringkasan)."""
    analyzer = get_news_analyzer()
    return analyzer.get_summary(symbol, days_back)

def get_numeric_sentiment(symbol, days_back=1):
    """Untuk skor numerik (-1..1)."""
    analyzer = get_news_analyzer()
    score, _ = analyzer.get_sentiment_score(symbol, days_back)
    return score