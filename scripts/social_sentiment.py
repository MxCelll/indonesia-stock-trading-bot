# scripts/social_sentiment.py
import logging
import praw
from textblob import TextBlob
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class SocialMediaAnalyzer:
    """
    Analis sentimen dari media sosial (Reddit saja karena Twitter API sulit).
    """
    def __init__(self):
        # Ambil credentials dari environment variable
        client_id = os.getenv('REDDIT_CLIENT_ID')
        client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        if not client_id or not client_secret:
            logger.warning("Reddit credentials tidak ditemukan di .env")
            self.reddit = None
        else:
            try:
                self.reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent="sentiment_bot by u/your_username"
                )
                logger.info("Reddit API initialized")
            except Exception as e:
                logger.error(f"Gagal inisialisasi Reddit: {e}")
                self.reddit = None
        
        self.subreddits = ["indonesia", "stocks", "investing", "finance"]
    
    def scrape_reddit(self, keyword, limit=20):
        """
        Mengambil postingan Reddit tentang keyword.
        """
        if self.reddit is None:
            return []
        posts = []
        try:
            # Bagi limit per subreddit
            per_sub = max(1, limit // len(self.subreddits))
            for sub in self.subreddits:
                try:
                    for post in self.reddit.subreddit(sub).search(keyword, limit=per_sub, sort='relevance'):
                        posts.append({
                            'date': datetime.fromtimestamp(post.created_utc),
                            'content': post.title + ' ' + (post.selftext if post.selftext else ''),
                            'score': post.score,
                            'comments': post.num_comments,
                            'source': 'reddit'
                        })
                except Exception as e:
                    logger.warning(f"Error di subreddit {sub}: {e}")
                    continue
            logger.info(f"Reddit: {len(posts)} posting untuk {keyword}")
        except Exception as e:
            logger.error(f"Gagal scrape Reddit: {e}")
        return posts
    
    def analyze_sentiment(self, text):
        """
        Analisis sentimen dengan TextBlob.
        """
        try:
            blob = TextBlob(text)
            return blob.sentiment.polarity  # -1..1
        except:
            return 0.0
    
    def get_social_sentiment(self, symbol, hours_back=24):
        """
        Menggabungkan sentimen dari Reddit.
        Mengembalikan skor rata-rata dan ringkasan.
        """
        clean_symbol = symbol.replace('.JK', '')
        posts = self.scrape_reddit(clean_symbol, limit=20)
        
        if not posts:
            return 0.0, "📱 Tidak ada diskusi di Reddit dalam 24 jam terakhir."
        
        # Hitung sentimen dengan bobot score
        sentiments = []
        for item in posts:
            text = item['content']
            sent = self.analyze_sentiment(text)
            # Bobot berdasarkan score (semakin banyak upvote, semakin berbobot)
            weight = 1 + (item['score'] / 10) if item['score'] > 0 else 1
            sentiments.append(sent * weight)
        
        avg_sentiment = sum(sentiments) / len(sentiments)
        
        pos_count = sum(1 for s in sentiments if s > 0.1)
        neg_count = sum(1 for s in sentiments if s < -0.1)
        neutral_count = len(sentiments) - pos_count - neg_count
        
        summary = f"📱 *Sentimen Reddit* ({len(sentiments)} posting)\n"
        summary += f"🟢 Positif: {pos_count}, ⚪ Netral: {neutral_count}, 🔴 Negatif: {neg_count}\n"
        summary += f"Skor rata-rata: {avg_sentiment:.2f}\n"
        
        return avg_sentiment, summary

# Singleton instance
_social_analyzer = None

def get_social_analyzer():
    global _social_analyzer
    if _social_analyzer is None:
        _social_analyzer = SocialMediaAnalyzer()
    return _social_analyzer

def get_social_sentiment(symbol):
    """Fungsi yang dipanggil dari agent framework."""
    analyzer = get_social_analyzer()
    return analyzer.get_social_sentiment(symbol)