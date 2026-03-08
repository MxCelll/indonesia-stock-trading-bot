# scripts/rekomendasi.py
import logging
import sqlite3
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from scripts.scoring_engine import ScoringEngine
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
from scripts.cache_manager import get_cache, set_cache
from scripts.formatters import format_rupiah, format_persen

logger = logging.getLogger(__name__)
scoring_engine = ScoringEngine()

# Cache untuk hasil scoring (expire 1 jam)
CACHE_DURATION = 3600

def get_active_symbols(min_volume=10000, min_data=50):
    """
    Mengambil daftar saham aktif (volume cukup dan data cukup).
    """
    conn = sqlite3.connect('data/saham.db')
    cursor = conn.cursor()
    
    # Ambil semua simbol dengan data historis
    cursor.execute("""
        SELECT Symbol, MAX(Date) as last_date, AVG(Volume) as avg_vol
        FROM saham
        GROUP BY Symbol
        HAVING COUNT(*) >= ? AND avg_vol >= ?
    """, (min_data, min_volume))
    
    symbols = [row[0] for row in cursor.fetchall()]
    conn.close()
    return symbols

def score_single_stock(symbol):
    """Wrapper untuk scoring dengan caching."""
    # Cek cache
    cache_key = f"stock_score_{symbol}"
    cached = get_cache(cache_key, max_age_seconds=CACHE_DURATION)
    if cached:
        return cached
    
    # Ambil data
    df = ambil_data_dari_db(symbol, hari=100)
    if df is None or len(df) < 50:
        return None
    
    df = tambah_indikator(df)
    result = scoring_engine.score_stock(symbol, df)
    
    if result:
        set_cache(cache_key, result)
    return result

def select_top_stocks(limit=5, max_workers=5, diversify_sectors=True):
    """
    Memilih saham terbaik dengan diversifikasi sektoral.
    """
    # Ambil daftar saham aktif
    symbols = get_active_symbols()
    logger.info(f"Memproses {len(symbols)} saham aktif...")
    
    # Hitung skor untuk semua
    scores = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sym = {executor.submit(score_single_stock, sym): sym for sym in symbols}
        for future in as_completed(future_to_sym):
            try:
                res = future.result(timeout=60)
                if res:
                    scores.append(res)
                    logger.info(f"Selesai: {res['symbol']} skor {res['total_score']:.1f}")
            except Exception as e:
                logger.error(f"Error: {e}")
    
    # Urutkan berdasarkan skor
    scores.sort(key=lambda x: x['total_score'], reverse=True)
    
    if not diversify_sectors:
        return scores[:limit]
    
    # Diversifikasi sektoral (ambil informasi sektor dari fundamental)
    sector_scores = defaultdict(list)
    for s in scores:
        # Kita perlu data sektor (bisa ditambahkan nanti)
        # Untuk sementara, asumsikan semua berbeda sektor
        sector = "unknown"
        sector_scores[sector].append(s)
    
    # Ambil top dari setiap sektor
    selected = []
    for sector, stocks in sector_scores.items():
        stocks.sort(key=lambda x: x['total_score'], reverse=True)
        if stocks:
            selected.append(stocks[0])
        if len(selected) >= limit:
            break
    
    return selected[:limit]

def format_recommendations(results):
    """Format hasil untuk Telegram dengan detail."""
    lines = ["🏆 *TOP 5 REKOMENDASI*\n"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. *{r['symbol']}* – {r['recommendation']}\n"
            f"   Harga: {format_rupiah(r['price'])} | Skor: {r['total_score']:.1f}\n"
            f"   Regime: {r['regime']}\n"
            f"   📊 T: {r['tech_score']:.0f} | F: {r['fund_score']:.0f} | S: {r['sent_score']:.0f} | ML: {r['ml_score']:.0f}\n"
            f"   ⚠️ Risiko: {r['risk_penalty']:.2f}\n"
        )
    return '\n'.join(lines)