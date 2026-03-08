import pandas as pd
import sqlite3
import os
import glob

DB_PATH = 'data/saham.db'
CSV_FOLDER = 'data_csv'

def parse_volume(vol_str):
    if pd.isna(vol_str) or vol_str == '-':
        return 0
    vol_str = str(vol_str).replace(',', '').strip()
    multiplier = 1
    if vol_str.endswith('K'):
        multiplier = 1_000
        vol_str = vol_str[:-1]
    elif vol_str.endswith('M'):
        multiplier = 1_000_000
        vol_str = vol_str[:-1]
    elif vol_str.endswith('B'):
        multiplier = 1_000_000_000
        vol_str = vol_str[:-1]
    try:
        return int(float(vol_str) * multiplier)
    except:
        return 0

def clean_price(price_str):
    if pd.isna(price_str):
        return 0.0
    cleaned = str(price_str).replace(',', '').replace(' ', '').strip()
    try:
        return float(cleaned)
    except:
        return 0.0

def import_csv_to_db(csv_file):
    print(f"\n📄 Memproses: {os.path.basename(csv_file)}")
    df = pd.read_csv(csv_file)
    print(f"Kolom yang ditemukan: {list(df.columns)}")

    if 'Price' in df.columns and 'Vol.' in df.columns:
        print("📌 Mendeteksi format Investing.com")
        for col in ['Open', 'High', 'Low', 'Price']:
            if col in df.columns:
                df[col] = df[col].apply(clean_price)
        df = df.rename(columns={'Price': 'Close', 'Vol.': 'Volume'})
        if 'Change %' in df.columns:
            df = df.drop(columns=['Change %'])
        df['Volume'] = df['Volume'].apply(parse_volume)
    else:
        column_map = {}
        for col in df.columns:
            col_lower = col.lower()
            if 'date' in col_lower:
                column_map[col] = 'Date'
            elif 'open' in col_lower:
                column_map[col] = 'Open'
            elif 'high' in col_lower:
                column_map[col] = 'High'
            elif 'low' in col_lower:
                column_map[col] = 'Low'
            elif 'close' in col_lower:
                column_map[col] = 'Close'
            elif 'volume' in col_lower:
                column_map[col] = 'Volume'
        df = df.rename(columns=column_map)
        for col in ['Open', 'High', 'Low', 'Close']:
            if col in df.columns:
                df[col] = df[col].apply(clean_price)

    required = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    missing = [col for col in required if col not in df.columns]
    if missing:
        print(f"❌ Kolom yang hilang: {missing}")
        return False

    try:
        df['Date'] = pd.to_datetime(df['Date'])
    except:
        df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')

    df = df.sort_values('Date')
    if len(df) < 30:
        print(f"⚠️ Peringatan: Hanya {len(df)} baris data. Mungkin kurang untuk analisis.")

    symbol = input(f"Masukkan kode saham untuk file {os.path.basename(csv_file)} (contoh: BBCA.JK): ").strip()
    if not symbol:
        print("❌ Kode saham tidak boleh kosong, lewati.")
        return False
    df['Symbol'] = symbol

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saham (
            Date TEXT,
            Open REAL,
            High REAL,
            Low REAL,
            Close REAL,
            Volume INTEGER,
            Symbol TEXT,
            PRIMARY KEY (Date, Symbol)
        )
    ''')
    conn.commit()

    cursor.execute("DELETE FROM saham WHERE Symbol = ?", (symbol,))
    conn.commit()

    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR REPLACE INTO saham (Date, Open, High, Low, Close, Volume, Symbol)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            row['Date'].strftime('%Y-%m-%d'),
            row['Open'],
            row['High'],
            row['Low'],
            row['Close'],
            int(row['Volume']),
            row['Symbol']
        ))
    conn.commit()
    conn.close()
    print(f"✅ Berhasil mengimpor {len(df)} baris untuk {symbol}")
    return True

def main():
    if not os.path.exists(CSV_FOLDER):
        print(f"Folder {CSV_FOLDER} tidak ditemukan. Buat folder tersebut dan masukkan file CSV di dalamnya.")
        return
    csv_files = glob.glob(os.path.join(CSV_FOLDER, '*.csv'))
    if not csv_files:
        print(f"Tidak ada file CSV di folder {CSV_FOLDER}")
        return
    print(f"Ditemukan {len(csv_files)} file CSV:")
    for f in csv_files:
        print(f"  - {os.path.basename(f)}")
    sukses = 0
    gagal = 0
    for csv_file in csv_files:
        if import_csv_to_db(csv_file):
            sukses += 1
        else:
            gagal += 1
    print("\n=== RINGKASAN IMPOR ===")
    print(f"Berhasil: {sukses}")
    print(f"Gagal: {gagal}")

if __name__ == "__main__":
    main()