# clean_database.py
import sqlite3

conn = sqlite3.connect('data/saham.db')
cursor = conn.cursor()

# Hapus baris dengan Date yang bukan format tanggal (string 'Ticker' atau kosong)
cursor.execute("DELETE FROM saham WHERE Date = 'Ticker' OR Date IS NULL OR Date = ''")
print(f"Baris dengan tanggal invalid: {cursor.rowcount} dihapus.")

# Opsional: hapus juga baris dengan harga tidak wajar (misal Open <= 0)
cursor.execute("DELETE FROM saham WHERE Open <= 0 OR Close <= 0")
print(f"Baris dengan harga tidak wajar: {cursor.rowcount} dihapus.")

conn.commit()
conn.close()
print("Database dibersihkan.")