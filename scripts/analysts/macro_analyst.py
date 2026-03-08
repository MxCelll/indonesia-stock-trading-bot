# scripts/analysts/macro_analyst.py
import pandas as pd
import logging
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
from scripts.economic_risk import get_current_risk_level
from scripts.sector_rotation import get_sector_analyzer

logger = logging.getLogger(__name__)

class MacroAnalyst:
    """
    Analis makro yang melihat kondisi pasar secara keseluruhan.
    - Tren IHSG
    - Rotasi sektor
    - Risiko ekonomi
    """
    def __init__(self):
        self.sector_analyzer = get_sector_analyzer()
    
    def analyze(self, symbol, df_ihsg=None):
        """
        Mengembalikan skor makro (0-100) untuk kondisi pasar.
        """
        reasons = []
        score = 50  # baseline
        
        # 1. Analisis IHSG
        if df_ihsg is None or df_ihsg.empty:
            df_ihsg = ambil_data_dari_db('JKSE', hari=100)
        
        if df_ihsg is not None and len(df_ihsg) > 20:
            df_ihsg = tambah_indikator(df_ihsg)
            latest = df_ihsg.iloc[-1]
            
            # Tren IHSG
            if latest['Close'] > latest['EMA20']:
                score += 15
                reasons.append("IHSG di atas EMA20 (+15)")
            else:
                score -= 10
                reasons.append("IHSG di bawah EMA20 (-10)")
            
            # RSI IHSG
            if latest['RSI'] > 70:
                score -= 10
                reasons.append("IHSG overbought (-10)")
            elif latest['RSI'] < 30:
                score += 10
                reasons.append("IHSG oversold (+10)")
        
        # 2. Rotasi sektor
        try:
            strong_sectors = self.sector_analyzer.get_strongest_sectors(top_n=3)
            if strong_sectors:
                # Cari apakah sektor saham ini termasuk kuat
                # Untuk sederhana, kita bisa cek dari nama saham
                # Atau perlu mapping sektor per saham (belum ada)
                score += 5
                reasons.append("Sektor terkuat terdeteksi (+5)")
        except:
            pass
        
        # 3. Risiko ekonomi
        risk = get_current_risk_level()
        if risk['risk_level'] == 'LOW':
            score += 10
            reasons.append("Risiko ekonomi rendah (+10)")
        elif risk['risk_level'] == 'MEDIUM':
            score += 0
            reasons.append("Risiko ekonomi sedang (0)")
        else:
            score -= 15
            reasons.append("Risiko ekonomi tinggi (-15)")
        
        # Normalisasi 0-100
        score = max(0, min(100, score))
        return {
            'score': score,
            'reasons': "; ".join(reasons),
            'risk_level': risk['risk_level']
        }