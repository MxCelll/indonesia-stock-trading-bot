# scripts/analysts/geopolitical_analyst.py
import logging
from scripts.geopolitical_risk import GeopoliticalRiskAnalyzer

logger = logging.getLogger(__name__)

class GeopoliticalAnalyst:
    """
    Analis risiko geopolitik global.
    """
    def __init__(self):
        self.analyzer = GeopoliticalRiskAnalyzer()
    
    def analyze(self, symbol, df):
        """
        Mengembalikan dict dengan prob_up, prob_down, confidence, reason.
        """
        risk_score, reason = self.analyzer.get_risk_score()
        # Konversi risk_score -1..1 ke probabilitas turun
        prob_down = (risk_score + 1) / 2
        prob_up = 1 - prob_down
        confidence = abs(risk_score) * 100
        return {
            'prob_up': prob_up,
            'prob_down': prob_down,
            'confidence': confidence,
            'reason': f"Geopolitik: {reason}"
        }