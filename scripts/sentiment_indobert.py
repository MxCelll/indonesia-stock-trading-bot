# scripts/sentiment_indobert.py
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import logging

logger = logging.getLogger(__name__)

class IndoBertSentiment:
    """
    Analisis sentimen untuk teks Bahasa Indonesia menggunakan model IndoBenchmark.
    Model: indobenchmark/indobert-base-p1 (dilatih untuk analisis sentimen)
    """
    def __init__(self, model_name='w11wo/indonesian-roberta-base-sentiment-classifier'):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
                num_labels=3  # positif, netral, negatif
            )
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Model sentimen dimuat: {model_name}")
        except Exception as e:
            logger.error(f"Gagal load model sentimen: {e}")
            self.model = None

    def predict_sentiment(self, text):
        """
        Mengembalikan skor sentimen antara -1 (negatif) hingga 1 (positif).
        """
        if self.model is None:
            return 0.0
        try:
            inputs = self.tokenizer(text, return_tensors='pt', truncation=True, max_length=512).to(self.device)
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
                # Asumsi label: 0 negatif, 1 netral, 2 positif
                neg_prob = probs[0][0].item()
                pos_prob = probs[0][2].item()
                # Skor: positif - negatif, hasil -1..1
                score = pos_prob - neg_prob
                return score
        except Exception as e:
            logger.error(f"Error prediksi sentimen: {e}")
            return 0.0

# Singleton
_sentiment_model = None

def get_sentiment_model():
    global _sentiment_model
    if _sentiment_model is None:
        _sentiment_model = IndoBertSentiment()
    return _sentiment_model