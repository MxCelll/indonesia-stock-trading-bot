# scripts/geopolitical_risk.py
import requests
import logging
from datetime import datetime, timedelta
import time
import random
from textblob import TextBlob

logger = logging.getLogger(__name__)

class GeopoliticalRiskAnalyzer:
    """
    Analis risiko geopolitik yang menggabungkan beberapa sumber:
    - Berita internasional (via NewsAPI)
    - Indeks VIX (via FRED) sebagai proksi ketidakpastian pasar
    - Sentimen berita global
    """
    def __init__(self):
        self.news_api_key = None  # akan diisi dari env
        self.fred_api_key = None
        self._load_api_keys()
    
    def _load_api_keys(self):
        import os
        from dotenv import load_dotenv
        load_dotenv()
        self.news_api_key = os.getenv('NEWS_API_KEY')
        self.fred_api_key = os.getenv('FRED_API_KEY')
    
    def get_geopolitical_news_sentiment(self, days_back=1):
        """
        Mengambil berita geopolitik internasional dan menghitung sentimen rata-rata.
        Keyword: 'geopolitical', 'conflict', 'war', 'tension', 'sanction'
        """
        if not self.news_api_key:
            logger.warning("NEWS_API_KEY tidak tersedia")
            return 0.0
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': 'geopolitical OR conflict OR war OR tension OR sanction',
            'from': start_date.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d'),
            'language': 'en',
            'sortBy': 'relevancy',
            'pageSize': 50,
            'apiKey': self.news_api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'ok' or data['totalResults'] == 0:
                return 0.0
            
            articles = data['articles']
            sentiments = []
            for article in articles:
                title = article.get('title') or ''
                description = article.get('description') or ''
                text = title + ' ' + description
                blob = TextBlob(text)
                sentiments.append(blob.sentiment.polarity)
            
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
            # Sentimen negatif -> risiko tinggi (kita balikkan skalanya)
            # Misal: sentimen -0.5 -> risiko 0.75
            risk_score = max(0, min(1, ( -avg_sentiment + 1 ) / 2))
            return risk_score
        except Exception as e:
            logger.error(f"Gagal mengambil berita geopolitik: {e}")
            return 0.0
    
    def get_vix_index(self):
        """
        Mengambil nilai VIX (CBOE Volatility Index) dari FRED sebagai ukuran ketidakpastian pasar.
        """
        if not self.fred_api_key:
            logger.warning("FRED_API_KEY tidak tersedia")
            return 0.5  # nilai default
        
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            'series_id': 'VIXCLS',
            'api_key': self.fred_api_key,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': 1
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            observations = data['observations']
            if observations:
                vix = float(observations[0]['value'])
                # Normalisasi VIX: 0-100 -> 0-1, biasanya VIX 10-40
                normalized = min(1, max(0, (vix - 10) / 30))
                return normalized
        except Exception as e:
            logger.error(f"Gagal mengambil VIX: {e}")
        return 0.5
    
    def get_combined_risk_score(self):
        """
        Menggabungkan beberapa sumber menjadi satu skor risiko (0-1).
        """
        news_risk = self.get_geopolitical_news_sentiment()
        vix_risk = self.get_vix_index()
        # Bobot: 60% berita, 40% VIX
        combined = 0.6 * news_risk + 0.4 * vix_risk
        return combined

# Singleton instance
_geopolitical_analyzer = None

def get_geopolitical_analyzer():
    global _geopolitical_analyzer
    if _geopolitical_analyzer is None:
        _geopolitical_analyzer = GeopoliticalRiskAnalyzer()
    return _geopolitical_analyzer

def get_geopolitical_risk():
    """
    Fungsi utama untuk mendapatkan skor risiko geopolitik (0-1) dan deskripsi.
    """
    analyzer = get_geopolitical_analyzer()
    score = analyzer.get_combined_risk_score()
    
    if score < 0.3:
        level = "RENDAH"
        desc = "Kondisi geopolitik relatif stabil."
    elif score < 0.6:
        level = "SEDANG"
        desc = "Ada beberapa ketegangan geopolitik."
    else:
        level = "TINGGI"
        desc = "Risiko geopolitik tinggi, waspadai volatilitas."
    
    return {
        'score': score,
        'level': level,
        'description': desc
    }