# scripts/create_strategy_table.py
import sqlite3
import logging

logger = logging.getLogger(__name__)

conn = sqlite3.connect('data/saham.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS strategy_experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        strategy_name TEXT,
        parameters TEXT,
        total_return REAL,
        win_rate REAL,
        profit_factor REAL,
        max_drawdown REAL,
        sharpe REAL,
        num_trades INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()
conn.close()
logger.info("Tabel strategy_experiments berhasil dibuat.")