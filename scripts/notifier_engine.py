# scripts/notifier_engine.py
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from scripts.analisis_adaptif import ambil_data_dari_db, tambah_indikator
from scripts.watchlist import load_watchlist
from scripts.notifier import kirim_notifikasi_sinkron
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# Ambil daftar saham dari watchlist
def get_watchlist_symbols():
    data = load_watchlist()
    return data['symbols']

# Cek apakah harga menyentuh support atau resistance
def check_support_resistance(df, current_price, threshold=0.005):
    """
    threshold: 0.5% dianggap menyentuh
    """
    support = df['Low'].tail(20).min()
    resistance = df['High'].tail(20).max()
    support_hit = abs(current_price - support) / support <= threshold
    resistance_hit = abs(current_price - resistance) / resistance <= threshold
    return support_hit, resistance_hit, support, resistance

# Cek volume spike
def check_volume_spike(df, factor=2.0):
    latest_vol = df.iloc[-1]['Volume']
    avg_vol = df['Volume'].tail(20).mean()
    return latest_vol > factor * avg_vol, latest_vol, avg_vol

# Cek RSI threshold
def check_rsi(df, oversold=30, overbought=70):
    rsi = df.iloc[-1]['RSI']
    is_oversold = rsi < oversold
    is_overbought = rsi > overbought
    return is_oversold, is_overbought, rsi

# Cek golden cross / death cross
def check_ema_cross(df):
    ema20 = df.iloc[-1]['EMA20']
    ema50 = df.iloc[-1]['EMA50']
    ema20_prev = df.iloc[-2]['EMA20'] if len(df) > 1 else None
    ema50_prev = df.iloc[-2]['EMA50'] if len(df) > 1 else None
    golden = False
    death = False
    if ema20_prev and ema50_prev:
        if ema20_prev <= ema50_prev and ema20 > ema50:
            golden = True
        if ema20_prev >= ema50_prev and ema20 < ema50:
            death = True
    return golden, death

def check_cluster_sentiment_changes(threshold=0.3):
    """
    Memeriksa perubahan sentimen klaster dan mengirim notifikasi jika ada perubahan signifikan.
    threshold: minimal perubahan absolut sentimen untuk dianggap signifikan (default 0.3).
    """
    conn = sqlite3.connect('data/saham.db')
    cursor = conn.cursor()
    
    # Ambil dua sentimen terakhir untuk setiap klaster
    cursor.execute('''
        SELECT cluster_name, symbols, avg_sentiment, updated_at 
        FROM cluster_sentiments 
        ORDER BY updated_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    if len(rows) < 2:
        return  # butuh minimal dua data untuk perbandingan
    
    # Kelompokkan berdasarkan cluster_name
    cluster_history = defaultdict(list)
    for row in rows:
        cluster_history[row[0]].append((row[2], row[3]))  # (sentiment, timestamp)
    
    alerts = []
    for cluster_name, history in cluster_history.items():
        if len(history) < 2:
            continue
        # Urutkan berdasarkan timestamp (asumsi sudah terurut descending, jadi history[0] adalah terbaru)
        latest = history[0][0]
        previous = history[1][0] if len(history) > 1 else latest
        change = latest - previous
        if abs(change) >= threshold:
            direction = "meningkat" if change > 0 else "menurun"
            alerts.append(
                f"🔔 Klaster {cluster_name} sentimen {direction} signifikan: "
                f"{previous:.2f} → {latest:.2f} (perubahan {change:+.2f})"
            )
    
    if alerts:
        message = "📊 *Perubahan Sentimen Klaster*\n\n" + "\n\n".join(alerts)
        kirim_notifikasi_sinkron(message)

# Fungsi utama untuk mengecek semua kondisi
def check_all_conditions():
    symbols = get_watchlist_symbols()
    alerts = []
    for sym in symbols:
        try:
            df = ambil_data_dari_db(sym, hari=50)
            if df is None or len(df) < 30:
                continue
            df = tambah_indikator(df)
            latest = df.iloc[-1]
            current_price = latest['Close']

            sup_hit, res_hit, sup, res = check_support_resistance(df, current_price)
            if sup_hit:
                alerts.append(f"🔔 {sym}: Menyentuh SUPPORT di Rp {sup:,.0f} (harga {current_price:,.0f})")
            if res_hit:
                alerts.append(f"🔔 {sym}: Menyentuh RESISTANCE di Rp {res:,.0f} (harga {current_price:,.0f})")

            vol_spike, vol, avg_vol = check_volume_spike(df)
            if vol_spike:
                alerts.append(f"🔔 {sym}: Volume Spike! ({vol:,.0f} vs rata2 {avg_vol:,.0f})")

            oversold, overbought, rsi = check_rsi(df)
            if oversold:
                alerts.append(f"🔔 {sym}: RSI Oversold ({rsi:.1f}) < 30")
            if overbought:
                alerts.append(f"🔔 {sym}: RSI Overbought ({rsi:.1f}) > 70")

            golden, death = check_ema_cross(df)
            if golden:
                alerts.append(f"🔔 {sym}: EMA Golden Cross (EMA20 naik di atas EMA50)")
            if death:
                alerts.append(f"🔔 {sym}: EMA Death Cross (EMA20 turun di bawah EMA50)")

        except Exception as e:
            logger.error(f"Error checking {sym}: {e}")
    return alerts

def run_notifier():
    """Fungsi yang dipanggil oleh scheduler"""
    alerts = check_all_conditions()
    if alerts:
        message = "🔔 *Notifikasi Otomatis*\n\n" + "\n\n".join(alerts)
        kirim_notifikasi_sinkron(message)
    else:
        logger.info(f"[{datetime.now().strftime('%H:%M')}] Tidak ada alert teknikal.")
    
    # Tambahkan notifikasi perubahan sentimen klaster
    check_cluster_sentiment_changes()