import sqlite3
import logging

logger = logging.getLogger(__name__)

def add_indexes():
    conn = sqlite3.connect('data/saham.db')
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON saham (Symbol)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON saham (Date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_date ON saham (Symbol, Date)")
    conn.commit()
    conn.close()
    logger.info("✅ Indeks berhasil ditambahkan ke database.")

if __name__ == "__main__":
    add_indexes()