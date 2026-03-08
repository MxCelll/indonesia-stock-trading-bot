# import_symbols.py
import sqlite3

# Baca file simbol
with open(r'C:\Users\MxCel\Documents\BotTradingSaham\idx-bei\python\symbols_from_json.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip()]

print(f"Total simbol: {len(symbols)}")

# Koneksi ke database
conn = sqlite3.connect('data/saham.db')
cursor = conn.cursor()

# Buat tabel jika belum ada
cursor.execute('''
    CREATE TABLE IF NOT EXISTS symbols (
        symbol TEXT PRIMARY KEY,
        is_active INTEGER DEFAULT 1
    )
''')

# Insert semua simbol
for sym in symbols:
    cursor.execute('INSERT OR IGNORE INTO symbols (symbol) VALUES (?)', (sym,))

conn.commit()
conn.close()

print("✅ Simbol berhasil ditambahkan ke database.")