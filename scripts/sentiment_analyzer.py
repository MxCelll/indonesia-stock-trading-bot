# scripts/sentiment_analyzer.py
import logging
import traceback
from datetime import datetime
import pandas as pd
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

logger.info("sentiment_analyzer.py: mulai")

try:
    import nltk
    logger.info("sentiment_analyzer.py: import nltk OK")
except Exception as e:
    logger.error(f"sentiment_analyzer.py: import nltk error: {e}")
    raise

try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    logger.info("sentiment_analyzer.py: import vader OK")
except Exception as e:
    logger.error(f"sentiment_analyzer.py: import vader error: {e}")
    raise

logger.info("sentiment_analyzer.py: import logging OK")
logger.info("sentiment_analyzer.py: import traceback OK")
logger.info("sentiment_analyzer.py: import datetime OK")
logger.info("sentiment_analyzer.py: import pandas OK")

# Setup logging (sebenarnya sudah ada di root, tapi kita tambahkan untuk jaga-jaga)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger.info("sentiment_analyzer.py: logging.basicConfig OK")

logger.info("sentiment_analyzer.py: sebelum definisi class SentimentAnalyzer")

class SentimentAnalyzer:
    """
    Analisis sentimen untuk berita menggunakan VADER dan FinBERT (jika tersedia).
    """
    
    def __init__(self, use_finbert: bool = True):
        print("sentiment_analyzer.py: in __init__", flush=True)
        try:
            self.vader = SentimentIntensityAnalyzer()
            print("sentiment_analyzer.py: VADER initialized", flush=True)
        except LookupError:
            print("sentiment_analyzer.py: downloading VADER lexicon...", flush=True)
            nltk.download('vader_lexicon')
            self.vader = SentimentIntensityAnalyzer()
            print("sentiment_analyzer.py: VADER initialized after download", flush=True)
        
        # Cek ketersediaan torch dan transformers hanya jika diperlukan
        self.use_finbert = use_finbert
        self._torch_available = False
        self._transformers_available = False
        self.tokenizer = None
        self.model = None
        
        if use_finbert:
            logger.info("sentiment_analyzer.py: use_finbert=True, mencoba import torch")
            try:
                import torch
                self._torch_available = True
                logger.info("sentiment_analyzer.py: import torch sukses di __init__")
            except Exception as e:
                logger.error(f"sentiment_analyzer.py: import torch error di __init__: {e}")
                self._torch_available = False
            
            if self._torch_available:
                try:
                    from transformers import AutoTokenizer, AutoModelForSequenceClassification
                    self._transformers_available = True
                    logger.info("sentiment_analyzer.py: import transformers sukses di __init__")
                except Exception as e:
                    logger.error(f"sentiment_analyzer.py: import transformers error di __init__: {e}")
                    self._transformers_available = False
            
            if self._torch_available and self._transformers_available:
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
                    self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
                    self.model.eval()
                    logger.info("sentiment_analyzer.py: FinBERT model loaded successfully")
                except Exception as e:
                    logger.error(f"sentiment_analyzer.py: Gagal load FinBERT: {e}. Fallback ke VADER.")
                    traceback.print_exc()
                    self.use_finbert = False
            else:
                self.use_finbert = False
                logger.info("sentiment_analyzer.py: FinBERT tidak dapat digunakan, fallback ke VADER")
        else:
            logger.info("sentiment_analyzer.py: use_finbert=False, hanya VADER")
    
    def analyze_vader(self, text: str) -> dict:
        scores = self.vader.polarity_scores(text)
        compound = scores['compound']
        if compound >= 0.05:
            label = 'positive'
        elif compound <= -0.05:
            label = 'negative'
        else:
            label = 'neutral'
        return {
            'compound': compound,
            'positive': scores['pos'],
            'negative': scores['neg'],
            'neutral': scores['neu'],
            'label': label,
            'confidence': abs(compound)
        }
    
    def analyze_finbert(self, text: str) -> dict:
        if not self.use_finbert or self.model is None:
            return self.analyze_vader(text)
        try:
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            pred = torch.argmax(probs, dim=-1).item()
            confidence = probs[0][pred].item()
            labels = ['negative', 'neutral', 'positive']
            label = labels[pred]
            return {
                'compound': (probs[0][2] - probs[0][0]).item(),
                'positive': probs[0][2].item(),
                'negative': probs[0][0].item(),
                'neutral': probs[0][1].item(),
                'label': label,
                'confidence': confidence
            }
        except Exception as e:
            logger.error(f"sentiment_analyzer.py: FinBERT error: {e}, fallback ke VADER")
            return self.analyze_vader(text)
    
    def analyze_news_batch(self, news_df: pd.DataFrame, text_column: str = 'title') -> pd.DataFrame:
        if news_df.empty:
            return news_df
        results = []
        for _, row in news_df.iterrows():
            text = row[text_column]
            if self.use_finbert:
                sent = self.analyze_finbert(text)
            else:
                sent = self.analyze_vader(text)
            row_dict = row.to_dict()
            row_dict.update({
                'sentiment_label': sent['label'],
                'sentiment_score': sent['compound'],
                'sentiment_confidence': sent['confidence'],
                'sentiment_positive': sent['positive'],
                'sentiment_negative': sent['negative'],
                'sentiment_neutral': sent['neutral'],
                'analyzed_at': datetime.now().isoformat()
            })
            results.append(row_dict)
        return pd.DataFrame(results)
    
    def get_cluster_sentiment(self, cluster_symbols: list, days_back: int = 7) -> dict:
        from scripts.news_cluster_fetcher import get_fetcher
        fetcher = get_fetcher()
        news_df = fetcher.fetch_news_for_symbols(cluster_symbols, days_back)
        if news_df.empty:
            return {
                'cluster': ','.join(cluster_symbols),
                'avg_sentiment': 0,
                'positive_ratio': 0,
                'negative_ratio': 0,
                'article_count': 0,
                'sentiment': 'neutral'
            }
        news_with_sent = self.analyze_news_batch(news_df)
        avg_score = news_with_sent['sentiment_score'].mean()
        pos_count = len(news_with_sent[news_with_sent['sentiment_label'] == 'positive'])
        neg_count = len(news_with_sent[news_with_sent['sentiment_label'] == 'negative'])
        total = len(news_with_sent)
        if avg_score > 0.1:
            sentiment = 'positive'
        elif avg_score < -0.1:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        return {
            'cluster': ','.join(cluster_symbols),
            'avg_sentiment': avg_score,
            'positive_ratio': pos_count / total if total > 0 else 0,
            'negative_ratio': neg_count / total if total > 0 else 0,
            'article_count': total,
            'sentiment': sentiment
        }

# Singleton instance
logger.info("sentiment_analyzer.py: sebelum singleton instance")
_analyzer_instance = None

def get_analyzer(use_finbert: bool = True):
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = SentimentAnalyzer(use_finbert=use_finbert)
    return _analyzer_instance

logger.info("sentiment_analyzer.py: selesai")