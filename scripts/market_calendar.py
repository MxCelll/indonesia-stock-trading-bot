# scripts/market_calendar.py
import sqlite3
from datetime import date

def is_market_open(check_date=None):
    """
    Mengecek apakah pasar buka pada tanggal tertentu.
    Menggunakan data libur nasional dari tabel indonesia_holidays.
    """
    if check_date is None:
        check_date = date.today()
    
    # Cek weekend (Sabtu=5, Minggu=6 dalam Python, Senin=0 Minggu=6)
    if check_date.weekday() >= 5:
        return False
    
    # Cek libur nasional di database
    conn = sqlite3.connect('data/saham.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM indonesia_holidays WHERE date = ?", (check_date.isoformat(),))
    count = cursor.fetchone()[0]
    conn.close()
    
    if count > 0:
        return False
    
    return True