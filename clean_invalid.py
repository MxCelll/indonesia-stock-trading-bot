# clean_invalid.py
import sqlite3

conn = sqlite3.connect('data/saham.db')
cursor = conn.cursor()

# Hapus baris dengan Date yang bukan format tanggal (misal 'Ticker')
cursor.execute("DELETE FROM saham WHERE Date = 'Ticker' OR Date IS NULL OR Date = ''")
print(f"Baris dihapus: {cursor.rowcount}")

conn.commit()
conn.close()