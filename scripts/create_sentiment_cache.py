# scripts/create_sentiment_cache.py
import sqlite3

def create_table():
    conn = sqlite3.connect('data/saham.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment_cache (
            symbol TEXT,
            date TEXT,
            source TEXT,
            score REAL,
            articles_count INTEGER,
            PRIMARY KEY (symbol, date)
        )
    ''')
    conn.commit()
    conn.close()
    print("Tabel sentiment_cache siap.")

if __name__ == "__main__":
    create_table()