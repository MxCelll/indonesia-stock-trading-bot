# save_symbols.py
import sqlite3

# Baca daftar dari file
with open('data/all_stocks_investpy.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip()]

# Tambahkan akhiran .JK
symbols_jk = [s + '.JK' for s in symbols]

# Simpan ke database
conn = sqlite3.connect('data/saham.db')
cursor = conn.cursor()

# Buat tabel jika belum ada
cursor.execute('''
    CREATE TABLE IF NOT EXISTS symbols (
        symbol TEXT PRIMARY KEY,
        name TEXT,
        is_active INTEGER DEFAULT 1
    )
''')

# Insert semua simbol
for sym in symbols_jk:
    cursor.execute('INSERT OR IGNORE INTO symbols (symbol) VALUES (?)', (sym,))

conn.commit()
conn.close()
print(f"✅ {len(symbols_jk)} simbol disimpan ke database.")