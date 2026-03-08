# scripts/optimize_db.py
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = 'data/saham.db'

def get_existing_indexes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='saham'")
    indexes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return indexes

def add_index_if_not_exists(index_name, table, columns):
    existing = get_existing_indexes()
    if index_name in existing:
        logger.info(f"Index {index_name} already exists.")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    sql = f"CREATE INDEX {index_name} ON {table} ({columns})"
    try:
        cursor.execute(sql)
        conn.commit()
        logger.info(f"Index {index_name} created.")
    except Exception as e:
        logger.error(f"Failed to create index {index_name}: {e}")
    finally:
        conn.close()

def add_all_indexes():
    # Indeks untuk tabel saham
    add_index_if_not_exists('idx_saham_symbol', 'saham', 'Symbol')
    add_index_if_not_exists('idx_saham_date', 'saham', 'Date')
    add_index_if_not_exists('idx_saham_symbol_date', 'saham', 'Symbol, Date')

    # Indeks untuk tabel fundamental_data (jika ada)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fundamental_data'")
    if cursor.fetchone():
        conn.close()
        add_index_if_not_exists('idx_fundamental_symbol', 'fundamental_data', 'symbol')
    else:
        conn.close()

    # Indeks untuk tabel news_cache (jika ada)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='news_cache'")
    if cursor.fetchone():
        add_index_if_not_exists('idx_news_symbol', 'news_cache', 'symbol')
        add_index_if_not_exists('idx_news_created', 'news_cache', 'created_at')
    conn.close()

    # Indeks untuk tabel trade_journal (jika sering diquery)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_journal'")
    if cursor.fetchone():
        add_index_if_not_exists('idx_journal_symbol', 'trade_journal', 'symbol')
        add_index_if_not_exists('idx_journal_status', 'trade_journal', 'status')
        add_index_if_not_exists('idx_journal_entry_date', 'trade_journal', 'entry_date')
    conn.close()

    logger.info("Database optimization completed.")

if __name__ == "__main__":
    add_all_indexes()