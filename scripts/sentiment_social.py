# scripts/sentiment_sentiment.py
import pandas as pd
import logging
from datetime import datetime, timedelta
from textblob import TextBlob
import snscrape.modules.twitter as sntwitter

logger = logging.getLogger(__name__)

def analyze_sentiment(text):
    """
    Analisis sentimen teks menggunakan TextBlob.
    Mengembalikan nilai antara -1 (negatif) dan 1 (positif).
    """
    try:
        blob = TextBlob(text)
        return blob.sentiment.polarity
    except Exception as e:
        logger.debug(f"Error analisis sentimen: {e}")
        return 0.0

def scrape_twitter(keyword, limit=100, hours=24):
    """
    Scrape tweet terbaru tentang suatu keyword (misal kode saham) dari Twitter.
    
    Args:
        keyword: kata kunci pencarian (misal 'BBCA' atau '$BBCA')
        limit: jumlah maksimal tweet yang diambil
        hours: rentang waktu ke belakang (jam)
    
    Returns:
        DataFrame dengan kolom: date, content, likes, retweets
    """
    tweets = []
    # Tentukan batas waktu
    since_date = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d')
    query = f"{keyword} since:{since_date} lang:id"  # bahasa Indonesia
    try:
        scraper = sntwitter.TwitterSearchScraper(query)
        for i, tweet in enumerate(scraper.get_items()):
            if i >= limit:
                break
            tweets.append({
                'date': tweet.date,
                'content': tweet.rawContent,
                'likes': tweet.likeCount,
                'retweets': tweet.retweetCount,
                'replies': tweet.replyCount,
            })
    except Exception as e:
        logger.error(f"Error scraping Twitter untuk {keyword}: {e}")
        return pd.DataFrame()
    
    return pd.DataFrame(tweets)

def get_social_sentiment(symbol, hours=24, limit=50):
    """
    Mendapatkan skor sentimen gabungan dari Twitter untuk suatu saham.
    
    Args:
        symbol: kode saham (misal 'BBCA.JK') – akan dibersihkan dari .JK
        hours: rentang waktu pencarian (jam)
        limit: jumlah tweet maksimal
    
    Returns:
        float: skor sentimen antara -1 (negatif) dan 1 (positif)
    """
    # Bersihkan simbol: hilangkan .JK dan mungkin tambahkan $ untuk pencarian
    clean_symbol = symbol.replace('.JK', '').upper()
    # Cari dengan dan tanpa $
    keywords = [clean_symbol, f"${clean_symbol}"]
    
    all_tweets = pd.DataFrame()
    for kw in keywords:
        df = scrape_twitter(kw, limit=limit//2, hours=hours)  # bagi limit agar total sekitar limit
        if not df.empty:
            all_tweets = pd.concat([all_tweets, df], ignore_index=True)
    
    if all_tweets.empty:
        logger.info(f"Tidak ada tweet untuk {symbol}")
        return 0.0
    
    # Analisis sentimen
    all_tweets['sentiment'] = all_tweets['content'].apply(analyze_sentiment)
    
    # Weighted average berdasarkan likes (engagement)
    total_likes = all_tweets['likes'].sum()
    if total_likes > 0:
        weighted_sent = (all_tweets['sentiment'] * all_tweets['likes']).sum() / total_likes
    else:
        weighted_sent = all_tweets['sentiment'].mean()
    
    logger.info(f"Sentimen sosial untuk {symbol}: {weighted_sent:.3f} dari {len(all_tweets)} tweet")
    return weighted_sent