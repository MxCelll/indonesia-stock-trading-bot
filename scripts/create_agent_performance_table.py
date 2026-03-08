# scripts/create_agent_performance_table.py
import sqlite3

conn = sqlite3.connect('data/saham.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS agent_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        date TEXT,
        agent_name TEXT,
        signal INTEGER,
        confidence REAL,
        actual_return REAL,
        regime TEXT
    )
''')
conn.commit()
conn.close()
print("✅ Tabel agent_performance siap.")