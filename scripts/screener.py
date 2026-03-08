# scripts/screener.py
import logging
import sqlite3
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
from scripts.formatters import format_rupiah, format_volume, format_rsi
from scripts.cache_manager import get_cache, set_cache

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def proses_satu_saham(symbol, filter_type):
    try:
        logging.info(f"Memproses {symbol}...")
        df = ambil_data_dari_db(symbol, hari=50)
        if df is None or len(df) < 30:
            logging.warning(f"{symbol}: Data tidak cukup (kurang dari 30 baris)")
            return None
        df = tambah_indikator(df)
        latest = df.iloc[-1]
        conditions = []
        vol_ma = df['Volume'].tail(20).mean()
        volume_ratio = latest['Volume'] / vol_ma if vol_ma > 0 else 0

        if latest['Volume'] > 2 * vol_ma:
            conditions.append('volume_spike')
        if latest['EMA20'] > latest['EMA50']:
            conditions.append('ema_golden_cross')
        if latest['EMA20'] < latest['EMA50']:
            conditions.append('ema_death_cross')
        if latest['RSI'] < 40:
            conditions.append('oversold')
        elif latest['RSI'] > 70:
            conditions.append('overbought')

        include = False
        if filter_type == 'all':
            include = True
        elif filter_type == 'oversold' and 'oversold' in conditions:
            include = True
        elif filter_type == 'overbought' and 'overbought' in conditions:
            include = True
        elif filter_type == 'volume_spike' and 'volume_spike' in conditions:
            include = True
        elif filter_type == 'golden_cross' and 'ema_golden_cross' in conditions:
            include = True
        elif filter_type == 'death_cross' and 'ema_death_cross' in conditions:
            include = True

        if include:
            score = 0
            if 'volume_spike' in conditions:
                score += 10
            if 'ema_golden_cross' in conditions:
                score += 5
            if 'oversold' in conditions:
                score += 3
            if 'overbought' in conditions:
                score += 3
            logging.info(f"{symbol} memenuhi kriteria dengan skor {score}")
            return {
                'symbol': symbol,
                'price': latest['Close'],
                'rsi': latest['RSI'],
                'volume': latest['Volume'],
                'vol_ma': vol_ma,
                'volume_ratio': volume_ratio,
                'conditions': conditions,
                'score': score
            }
        logging.info(f"{symbol} tidak memenuhi kriteria")
        return None
    except Exception as e:
        logging.error(f"Error processing {symbol}: {e}")
        return None

def get_screener_results(filter_type='all', custom_filters=None, sort_by='score', use_cache=True, limit=None):
    """
    Menjalankan screener dan mengembalikan hasil.
    limit: jumlah maksimal hasil yang dikembalikan (None = semua).
    """
    cache_key = f"screener_{filter_type}_{sort_by}_{limit}"
    if use_cache:
        cached = get_cache(cache_key)
        if cached is not None:
            logging.info(f"📦 Memuat hasil screener dari cache")
            return cached

    conn = sqlite3.connect('data/saham.db')
    query = "SELECT DISTINCT Symbol FROM saham"
    symbols = pd.read_sql(query, conn)['Symbol'].tolist()
    conn.close()
    logging.info(f"Memproses {len(symbols)} saham...")

    results = []
    # Kurangi jumlah worker untuk menghindari overload
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_sym = {executor.submit(proses_satu_saham, sym, filter_type): sym for sym in symbols}
        for future in as_completed(future_to_sym):
            try:
                # Timeout per task 30 detik
                res = future.result(timeout=30)
                if res:
                    results.append(res)
            except TimeoutError:
                logging.warning(f"Timeout saat memproses {future_to_sym[future]}")
            except Exception as e:
                logging.error(f"Error processing {future_to_sym[future]}: {e}")

    logging.info(f"Screener selesai, ditemukan {len(results)} saham")

    if sort_by == 'score':
        results.sort(key=lambda x: -x['score'])
    elif sort_by == 'volume':
        results.sort(key=lambda x: -x['volume'])
    elif sort_by == 'rsi_asc':
        results.sort(key=lambda x: x['rsi'])
    elif sort_by == 'rsi_desc':
        results.sort(key=lambda x: -x['rsi'])
    
    # Terapkan limit jika diberikan
    if limit is not None and limit > 0:
        results = results[:limit]
    
    if use_cache:
        set_cache(cache_key, results)
    return results

def format_screener(results, filter_name, custom_desc=""):
    if not results:
        return f"🔍 *Screener: {filter_name}*{custom_desc}\n\nTidak ada saham yang memenuhi kriteria."
    lines = [f"🔍 *Screener: {filter_name}*{custom_desc} (Total: {len(results)} saham)\n"]
    for r in results:
        cond_str = ', '.join(r['conditions']).replace('_', ' ')
        vol_ratio = r['volume_ratio']
        vol_arrow = "🔥" if vol_ratio > 2 else "📊" if vol_ratio > 1.5 else "💧"
        rsi_color = "🟢" if r['rsi'] < 30 else "🔴" if r['rsi'] > 70 else "⚪"
        lines.append(
            f"• *{r['symbol']}* (skor: {r['score']})\n"
            f"  💵 Harga: {format_rupiah(r['price'])}\n"
            f"  {rsi_color} RSI: {r['rsi']:.1f}\n"
            f"  {vol_arrow} Volume: {format_volume(r['volume'])} ({vol_ratio:.1f}x MA)\n"
            f"  🏷️ Kondisi: {cond_str}\n"
        )
    return '\n'.join(lines)