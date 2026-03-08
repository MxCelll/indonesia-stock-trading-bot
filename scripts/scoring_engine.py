# scripts/scoring_engine.py
import logging
import numpy as np
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
from scripts.fundamental import get_fundamental_data, fundamental_score
from scripts.sentiment_news import get_news_analyzer
from scripts.ml_predictor_advanced import get_predictor
from scripts.lstm_predictor import predict_lstm
from scripts.regime_classifier import get_regime_classifier

logger = logging.getLogger(__name__)

class ScoringEngine:
    """
    Mesin scoring adaptif yang menyesuaikan bobot berdasarkan regime pasar.
    """
    def __init__(self):
        self.regime_classifier = get_regime_classifier()
        self.news_analyzer = get_news_analyzer()
        
        # Bobot dasar untuk setiap regime
        self.weights = {
            'trending_bull': {
                'teknikal': 0.45,
                'fundamental': 0.15,
                'sentimen': 0.10,
                'ml': 0.30,
                'risiko': -0.05  # penalti
            },
            'trending_bear': {
                'teknikal': 0.40,
                'fundamental': 0.20,
                'sentimen': 0.15,
                'ml': 0.25,
                'risiko': -0.10
            },
            'sideways': {
                'teknikal': 0.30,
                'fundamental': 0.30,
                'sentimen': 0.20,
                'ml': 0.20,
                'risiko': -0.05
            },
            'high_volatility': {
                'teknikal': 0.25,
                'fundamental': 0.15,
                'sentimen': 0.15,
                'ml': 0.25,
                'risiko': -0.20
            },
            'unknown': {
                'teknikal': 0.35,
                'fundamental': 0.25,
                'sentimen': 0.15,
                'ml': 0.25,
                'risiko': -0.10
            }
        }
    
    def get_weights(self, regime):
        """Mengembalikan bobot untuk regime tertentu."""
        return self.weights.get(regime, self.weights['unknown'])
    
    def calculate_risk_penalty(self, symbol, df):
        """
        Menghitung penalti berdasarkan risiko.
        - Volatilitas tinggi -> penalti besar
        - Volume rendah -> penalti
        """
        latest = df.iloc[-1]
        atr = latest.get('ATR', 0)
        price = latest['Close']
        
        # Volatilitas relatif (ATR/Price)
        vol_ratio = atr / price if price > 0 else 0
        
        # Volume relatif terhadap rata-rata
        vol = latest['Volume']
        avg_vol = df['Volume'].tail(20).mean()
        vol_ratio_volume = vol / avg_vol if avg_vol > 0 else 0
        
        # Likuiditas (volume rendah -> penalti)
        liquidity_penalty = max(0, 1 - vol_ratio_volume) * 0.5
        
        # Volatilitas tinggi -> penalti
        vol_penalty = min(1, vol_ratio * 10) * 0.5
        
        total_penalty = (liquidity_penalty + vol_penalty) / 2
        return total_penalty
    
    def score_stock(self, symbol, df):
        """
        Menghitung skor komposit untuk satu saham.
        """
        try:
            # 1. Dapatkan regime pasar
            regime = self.regime_classifier.predict_regime(df)
            weights = self.get_weights(regime)
            
            # 2. Skor Teknikal (dari sinyal dasar atau multi-agent)
            latest = df.iloc[-1]
            rsi = latest.get('RSI', 50)
            if rsi < 30:
                tech_score = 80 + (30 - rsi) * 2
            elif rsi > 70:
                tech_score = 20
            else:
                tech_score = 50 + (rsi - 50)
            tech_score = max(0, min(100, tech_score))
            
            # 3. Skor Fundamental
            fundamental = get_fundamental_data(symbol)
            if fundamental:
                fund_score, _ = fundamental_score(fundamental)
            else:
                fund_score = 50
            
            # 4. Skor Sentimen
            sentimen, _ = self.news_analyzer.get_sentiment_score(symbol, days_back=1)
            sent_score = (sentimen + 1) * 50  # konversi -1..1 ke 0..100
            
            # 5. Skor ML (gabungan XGBoost + LSTM)
            ml_scores = []
            # XGBoost
            predictor = get_predictor(symbol, target_days=5)
            if predictor:
                direction, confidence = predictor.predict()
                if direction == 1:
                    ml_scores.append(confidence)
                elif direction == -1:
                    ml_scores.append(100 - confidence)
                else:
                    ml_scores.append(50)
            
            # LSTM (jika ada)
            lstm_dir, lstm_conf, _, _ = predict_lstm(symbol)
            if lstm_dir != 0:
                if lstm_dir == 1:
                    ml_scores.append(lstm_conf)
                elif lstm_dir == -1:
                    ml_scores.append(100 - lstm_conf)
            
            ml_score = np.mean(ml_scores) if ml_scores else 50
            
            # 6. Penalti Risiko
            risk_penalty = self.calculate_risk_penalty(symbol, df)
            
            # 7. Skor Total dengan bobot dinamis
            total_score = (
                weights['teknikal'] * tech_score +
                weights['fundamental'] * fund_score +
                weights['sentimen'] * sent_score +
                weights['ml'] * ml_score
            ) * (1 - risk_penalty * weights['risiko'])
            
            # 8. Normalisasi ke 0-100
            total_score = max(0, min(100, total_score))
            
            # 9. Tentukan rekomendasi
            if total_score >= 70:
                recommendation = "🔴 BELI"
            elif total_score <= 30:
                recommendation = "🔵 JUAL"
            else:
                recommendation = "⚪ TAHAN"
            
            return {
                'symbol': symbol,
                'price': latest['Close'],
                'regime': regime,
                'tech_score': tech_score,
                'fund_score': fund_score,
                'sent_score': sent_score,
                'ml_score': ml_score,
                'risk_penalty': risk_penalty,
                'total_score': total_score,
                'recommendation': recommendation
            }
        except Exception as e:
            logger.error(f"Error scoring {symbol}: {e}")
            return None