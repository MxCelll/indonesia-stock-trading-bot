# scripts/rekomendasi.py
import logging
import sqlite3
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
from scripts.signal_scorer import SignalScorer
from scripts.multi_tf import get_tf_analysis_v2
from scripts.fundamental import get_fundamental_data, fundamental_score
from scripts.sentiment_news import get_news_analyzer
from scripts.ml_predictor_advanced import get_predictor
from scripts.lstm_predictor import predict_lstm
from scripts.formatters import format_rupiah, format_persen

logger = logging.getLogger(__name__)
scorer = SignalScorer()
news_analyzer = get_news_analyzer()

def hitung_skor_teknikal(symbol, df):
    """Menghitung skor teknikal menggunakan SignalScorer."""
    latest = df.iloc[-1]
    data = {
        'rsi': latest['RSI'],
        'macd': latest['MACD'],
        'macd_signal': latest['MACD_signal'],
        'macd_hist': latest['MACD_diff'],
        'price': latest['Close'],
        'ema20': latest['EMA20'],
        'ema50': latest['EMA50'],
        'volume': latest['Volume'],
        'avg_volume': latest['Volume_MA20'],
        'adx': latest['ADX'],
        'di_plus': latest['DI_plus'],
        'di_minus': latest['DI_minus']
    }
    # Asumsikan target direction 'buy' untuk skor (bisa disesuaikan)
    skor = scorer.calculate_score(data, None, target_direction='buy')
    return skor

def hitung_skor_saham(symbol):
    """Menghitung skor komposit untuk satu saham."""
    try:
        # Ambil data historis 100 hari
        df = ambil_data_dari_db(symbol, hari=100)
        if df is None or len(df) < 50:
            return None
        
        df = tambah_indikator(df)
        
        # 1. Skor Teknikal (40% bobot)
        skor_teknikal = hitung_skor_teknikal(symbol, df)
        
        # 2. Skor Multi-timeframe (20% bobot)
        try:
            tf_result, _ = get_tf_analysis_v2(symbol, target_direction='buy')
            if tf_result:
                skor_tf = tf_result['total_score']
            else:
                skor_tf = 50
        except:
            skor_tf = 50
        
        # 3. Skor Fundamental (15% bobot)
        fundamental = get_fundamental_data(symbol)
        if fundamental:
            skor_fundamental, _ = fundamental_score(fundamental)
        else:
            skor_fundamental = 50
        
        # 4. Sentimen Berita (10% bobot)
        sentimen, _ = news_analyzer.get_sentiment_score(symbol, days_back=1)
        # Konversi sentimen -1..1 ke skor 0..100
        skor_sentimen = (sentimen + 1) * 50
        
        # 5. Prediksi ML (15% bobot)
        # Coba XGBoost dulu
        predictor = get_predictor(symbol, target_days=5)
        if predictor:
            direction, confidence = predictor.predict()
            # Konversi arah dan confidence ke skor
            if direction == 1:
                skor_ml = confidence
            elif direction == -1:
                skor_ml = 100 - confidence
            else:
                skor_ml = 50
        else:
            skor_ml = 50
        
        # Bobot total
        skor_total = (
            0.4 * skor_teknikal +
            0.2 * skor_tf +
            0.15 * skor_fundamental +
            0.1 * skor_sentimen +
            0.15 * skor_ml
        )
        
        return {
            'symbol': symbol,
            'price': df.iloc[-1]['Close'],
            'skor_teknikal': skor_teknikal,
            'skor_tf': skor_tf,
            'skor_fundamental': skor_fundamental,
            'skor_sentimen': skor_sentimen,
            'skor_ml': skor_ml,
            'skor_total': skor_total,
            'rekomendasi': 'BELI' if skor_total > 70 else ('JUAL' if skor_total < 30 else 'Tahan')
        }
    except Exception as e:
        logger.error(f"Gagal memproses {symbol}: {e}")
        return None

def scan_semua_saham(limit=5, max_workers=5):
    """
    Memindai semua saham di database, menghitung skor, dan mengembalikan top N.
    """
    # Ambil semua simbol
    conn = sqlite3.connect('data/saham.db')
    cursor = conn.cursor()
    cursor.execute("SELECT symbol FROM symbols")
    symbols = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    logger.info(f"Memulai scanning {len(symbols)} saham...")
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_symbol = {executor.submit(hitung_skor_saham, sym): sym for sym in symbols}
        for future in as_completed(future_to_symbol):
            res = future.result(timeout=30)
            if res:
                results.append(res)
                logger.info(f"Selesai: {res['symbol']} skor {res['skor_total']:.1f}")
    
    # Urutkan berdasarkan skor total
    results.sort(key=lambda x: x['skor_total'], reverse=True)
    
    return results[:limit]

def format_rekomendasi(results):
    """Format hasil rekomendasi untuk ditampilkan di Telegram."""
    lines = ["🏆 *TOP 5 REKOMENDASI SAHAM*\n"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. *{r['symbol']}* – Skor: {r['skor_total']:.1f} – {r['rekomendasi']}\n"
            f"   Harga: {format_rupiah(r['price'])} | T: {r['skor_teknikal']:.0f} | MTF: {r['skor_tf']:.0f} | F: {r['skor_fundamental']:.0f} | S: {r['skor_sentimen']:.0f} | ML: {r['skor_ml']:.0f}\n"
        )
    return '\n'.join(lines)