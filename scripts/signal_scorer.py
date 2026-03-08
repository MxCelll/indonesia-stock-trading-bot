# scripts/signal_scorer.py
import numpy as np

class SignalScorer:
    def __init__(self):
        self.weights = {
            'rsi': 15,
            'macd': 15,
            'ema': 10,
            'volume': 10,
            'adx': 10,
            'price_action': 10,
            'ai': 15,
            'fundamental': 5,
            'cluster_sentiment': 5,
            'ml_prediction': 5
        }

    def _score_rsi(self, rsi, target_direction='buy'):
        if target_direction == 'buy':
            if rsi < 30:
                return 100
            elif rsi < 40:
                return 80
            elif rsi < 50:
                return 60
            elif rsi < 60:
                return 40
            else:
                return 20
        else:
            if rsi > 70:
                return 100
            elif rsi > 60:
                return 80
            elif rsi > 50:
                return 60
            elif rsi > 40:
                return 40
            else:
                return 20

    def _score_macd(self, macd, signal, hist, target_direction='buy'):
        if target_direction == 'buy':
            if macd > signal and hist > 0:
                return 100
            elif macd > signal:
                return 70
            elif macd < signal and hist < 0:
                return 20
            else:
                return 50
        else:
            if macd < signal and hist < 0:
                return 100
            elif macd < signal:
                return 70
            elif macd > signal and hist > 0:
                return 20
            else:
                return 50

    def _score_ema(self, price, ema20, ema50, target_direction='buy'):
        if target_direction == 'buy':
            if price > ema20 > ema50:
                return 100
            elif price > ema20:
                return 70
            elif price > ema50:
                return 40
            else:
                return 10
        else:
            if price < ema20 < ema50:
                return 100
            elif price < ema20:
                return 70
            elif price < ema50:
                return 40
            else:
                return 10

    def _score_volume(self, volume, avg_volume, target_direction='buy'):
        ratio = volume / avg_volume if avg_volume > 0 else 1
        if target_direction == 'buy':
            if ratio > 2:
                return 100
            elif ratio > 1.5:
                return 80
            elif ratio > 1.2:
                return 60
            elif ratio > 1:
                return 40
            else:
                return 20
        else:
            if ratio > 2:
                return 100
            elif ratio > 1.5:
                return 80
            elif ratio > 1.2:
                return 60
            elif ratio > 1:
                return 40
            else:
                return 20

    def _score_adx(self, adx, di_plus, di_minus, target_direction='buy'):
        if adx > 25:
            if target_direction == 'buy' and di_plus > di_minus:
                return 100
            elif target_direction == 'sell' and di_minus > di_plus:
                return 100
            else:
                return 50
        else:
            return 30

    def _score_price_action(self, price, ema20, target_direction='buy'):
        distance = (price - ema20) / ema20 * 100
        if target_direction == 'buy':
            if 0 < distance < 2:
                return 100
            elif distance > 5:
                return 30
            elif distance < 0:
                return 20
            else:
                return 60
        else:
            if -2 < distance < 0:
                return 100
            elif distance < -5:
                return 30
            elif distance > 0:
                return 20
            else:
                return 60

    def _score_ai(self, ai_result, target_direction='buy'):
        if not ai_result:
            return 50
        rec = ai_result.get('recommendation', '').lower()
        conf = ai_result.get('confidence', 0)
        if target_direction == 'buy':
            if rec == 'buy':
                return conf
            elif rec == 'sell':
                return 100 - conf
            else:
                return 50
        else:
            if rec == 'sell':
                return conf
            elif rec == 'buy':
                return 100 - conf
            else:
                return 50

    def _score_fundamental(self, fundamental_score):
        return fundamental_score

    def _score_cluster_sentiment(self, sentiment_score):
        # Konversi dari -1..1 ke 0..100
        return (sentiment_score + 1) * 50

    def _score_ml_prediction(self, ml_direction, ml_confidence, target_direction='buy'):
        if ml_direction is None:
            return 50
        if target_direction == 'buy':
            if ml_direction == 1:
                return ml_confidence
            else:
                return 100 - ml_confidence
        else:
            if ml_direction == -1:
                return ml_confidence
            else:
                return 100 - ml_confidence

    def calculate_score(self, data, ai_result, fundamental_score=None, cluster_sentiment=None,
                        ml_prediction=None, ml_confidence=None, target_direction='buy'):
        """
        Menghitung skor total (0-100) berdasarkan data teknikal, AI, fundamental, sentimen klaster, dan prediksi ML.
        """
        scores = {}
        scores['rsi'] = self._score_rsi(data['rsi'], target_direction)
        scores['macd'] = self._score_macd(data['macd'], data['macd_signal'], data['macd_hist'], target_direction)
        scores['ema'] = self._score_ema(data['price'], data['ema20'], data['ema50'], target_direction)
        scores['volume'] = self._score_volume(data['volume'], data['avg_volume'], target_direction)
        scores['adx'] = self._score_adx(data['adx'], data['di_plus'], data['di_minus'], target_direction)
        scores['price_action'] = self._score_price_action(data['price'], data['ema20'], target_direction)
        scores['ai'] = self._score_ai(ai_result, target_direction)
        if fundamental_score is not None:
            scores['fundamental'] = self._score_fundamental(fundamental_score)
        else:
            scores['fundamental'] = 50
        if cluster_sentiment is not None:
            scores['cluster_sentiment'] = self._score_cluster_sentiment(cluster_sentiment)
        else:
            scores['cluster_sentiment'] = 50
        if ml_prediction is not None and ml_confidence is not None:
            scores['ml_prediction'] = self._score_ml_prediction(ml_prediction, ml_confidence, target_direction)
        else:
            scores['ml_prediction'] = 50

        total_weight = sum(self.weights.values())
        weighted_sum = sum(scores[key] * self.weights.get(key, 0) for key in scores)
        final_score = weighted_sum / total_weight
        return round(final_score, 1)