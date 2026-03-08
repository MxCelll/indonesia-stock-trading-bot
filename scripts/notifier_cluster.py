# scripts/notifier_cluster.py
import sqlite3
import logging
from datetime import datetime, timedelta
from scripts.notifier import kirim_notifikasi_sinkron

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_new_clusters(since_hours: int = 24, db_path='data/saham.db') -> list:
    """
    Mendapatkan klaster yang terdeteksi dalam 24 jam terakhir.
    """
    cutoff = (datetime.now() - timedelta(hours=since_hours)).isoformat()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT cluster_name, symbols, detected_at FROM news_clusters
        WHERE detected_at >= ?
    ''', (cutoff,))
    rows = cursor.fetchall()
    conn.close()
    return [{'name': r[0], 'symbols': r[1].split(','), 'detected_at': r[2]} for r in rows]

def get_significant_sentiment_changes(threshold: float = 0.3, since_hours: int = 24, db_path='data/saham.db') -> list:
    """
    Mendapatkan perubahan sentimen signifikan (misal dari netral ke positif/negatif atau perubahan besar).
    threshold: perubahan absolut avg_sentiment minimal.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Ambil dua data terbaru per cluster (jika ada)
    cursor.execute('''
        SELECT cs1.cluster_name, cs1.symbols, cs1.avg_sentiment, cs2.avg_sentiment
        FROM cluster_sentiments cs1
        LEFT JOIN cluster_sentiments cs2 ON cs1.cluster_name = cs2.cluster_name
            AND cs2.updated_at < cs1.updated_at
        WHERE cs1.updated_at >= ?
        GROUP BY cs1.cluster_name
        ORDER BY cs1.updated_at DESC
    ''', ((datetime.now() - timedelta(hours=since_hours)).isoformat(),))
    rows = cursor.fetchall()
    conn.close()
    changes = []
    for name, symbols, latest, prev in rows:
        if prev is not None and abs(latest - prev) >= threshold:
            changes.append({
                'cluster': name,
                'symbols': symbols.split(','),
                'old_sentiment': prev,
                'new_sentiment': latest,
                'change': latest - prev
            })
    return changes

def run_cluster_notifier():
    """
    Fungsi yang dipanggil oleh scheduler untuk memeriksa notifikasi klaster.
    """
    new_clusters = get_new_clusters(since_hours=24)
    if new_clusters:
        msg = "🔔 *Klaster Baru Terdeteksi!*\n\n"
        for c in new_clusters:
            msg += f"• {c['name']}: {', '.join(c['symbols'][:5])}"
            if len(c['symbols']) > 5:
                msg += f" dan {len(c['symbols'])-5} lainnya"
            msg += f"\n  Terdeteksi: {c['detected_at'][:16]}\n\n"
        kirim_notifikasi_sinkron(msg)

    changes = get_significant_sentiment_changes(threshold=0.3, since_hours=24)
    if changes:
        msg = "📈 *Perubahan Sentimen Signifikan!*\n\n"
        for ch in changes:
            direction = "🟢 positif" if ch['change'] > 0 else "🔴 negatif"
            msg += f"• {ch['cluster']}\n"
            msg += f"  Sentimen: {ch['old_sentiment']:.2f} → {ch['new_sentiment']:.2f} ({direction})\n"
            msg += f"  Saham: {', '.join(ch['symbols'][:5])}\n\n"
        kirim_notifikasi_sinkron(msg)