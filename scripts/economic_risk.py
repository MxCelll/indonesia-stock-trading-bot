# scripts/economic_risk.py
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

def get_current_risk_level(db_path: str = 'data/saham.db') -> dict:
    """
    Menganalisis data ekonomi terkini dan mengembalikan level risiko.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ambil data ekonomi terbaru (7 hari terakhir)
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT * FROM economic_data
        WHERE date >= ?
        ORDER BY date DESC
    ''', (one_week_ago,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {
            'risk_level': 'LOW',
            'message': 'Tidak ada data ekonomi signifikan dalam 7 hari terakhir.'
        }

    # Analisis dampak
    high_impact_events = 0
    for row in rows:
        # row: id, date, series_id, description, actual, previous, change, impact, updated_at
        impact = row[7]
        if impact == 'High':
            high_impact_events += 1

    if high_impact_events >= 3:
        risk_level = 'HIGH'
        message = f'Terdapat {high_impact_events} rilis data ber-impact tinggi dalam 7 hari terakhir. Disarankan mengurangi ukuran posisi.'
    elif high_impact_events >= 1:
        risk_level = 'MEDIUM'
        message = f'Terdapat {high_impact_events} rilis data ber-impact tinggi. Waspada volatilitas.'
    else:
        risk_level = 'LOW'
        message = 'Tidak ada rilis data ber-impact tinggi. Kondisi relatif aman.'

    return {
        'risk_level': risk_level,
        'high_impact_count': high_impact_events,
        'message': message,
        'data': rows
    }

def should_reduce_position(db_path: str = 'data/saham.db') -> bool:
    """
    Menentukan apakah ukuran posisi harus dikurangi berdasarkan data ekonomi.
    """
    risk = get_current_risk_level(db_path)
    # Kurangi posisi jika risiko HIGH
    return risk['risk_level'] == 'HIGH'

def should_block_trading(db_path: str = 'data/saham.db') -> bool:
    """
    Menentukan apakah trading harus diblokir sementara.
    (Contoh: jika ada rilis data sangat penting dalam 30 menit ke depan)
    """
    # Implementasi lebih lanjut bisa menggunakan jadwal rilis real-time
    # Untuk sekarang, kita hanya blokir jika ada data high impact dalam 1 hari terakhir
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT COUNT(*) FROM economic_data
        WHERE date = ? AND impact = 'High'
    ''', (today,))
    count = cursor.fetchone()[0]
    conn.close()

    return count > 0