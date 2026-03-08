import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

def setup_database():
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect('data/saham.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            entry_date TEXT,
            entry_price REAL,
            entry_size INTEGER,
            exit_date TEXT,
            exit_price REAL,
            exit_size INTEGER,
            pnl REAL,
            pnl_percent REAL,
            signal_reason TEXT,
            ai_recommendation TEXT,
            ai_confidence INTEGER,
            screenshot TEXT,
            emotion_entry INTEGER,
            emotion_exit INTEGER,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ Tabel 'trades' berhasil dibuat (jika belum ada).")

if __name__ == "__main__":
    setup_database()