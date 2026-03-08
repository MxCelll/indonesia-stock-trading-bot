# scripts/economic_fetcher.py
import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from fredapi import Fred
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

FRED_API_KEY = os.getenv('FRED_API_KEY')
if not FRED_API_KEY:
    raise ValueError("FRED_API_KEY tidak ditemukan di file .env. Tambahkan baris: FRED_API_KEY=your_key_here")

class EconomicFetcher:
    """
    Fetcher untuk data ekonomi dari FRED.
    """
    def __init__(self):
        self.fred = Fred(api_key=FRED_API_KEY)

    def get_series_data(self, series_id: str, observation_start: str = None, observation_end: str = None) -> pd.DataFrame:
        """
        Mengambil data time series dari FRED.
        Contoh series_id: 'FEDFUNDS' (suku bunga), 'CPIAUCSL' (inflasi), 'GDP' (PDB).
        """
        try:
            data = self.fred.get_series(series_id, observation_start=observation_start, observation_end=observation_end)
            # Konversi ke DataFrame dengan kolom date dan value
            df = data.reset_index()
            df.columns = ['date', 'value']
            df['series_id'] = series_id
            return df
        except Exception as e:
            logging.error(f"Gagal mengambil data series {series_id}: {e}")
            return pd.DataFrame()

    def get_releases(self, limit: int = 10) -> pd.DataFrame:
        """
        Mengambil daftar rilis data ekonomi terbaru.
        (Tidak semua rilis penting, tapi bisa jadi referensi)
        """
        try:
            releases = self.fred.get_releases()
            return releases.head(limit)
        except Exception as e:
            logging.error(f"Gagal mengambil releases: {e}")
            return pd.DataFrame()

    def get_economic_calendar(self, days_ahead: int = 7) -> pd.DataFrame:
        """
        Simulasi kalender ekonomi.
        Karena FRED tidak punya endpoint kalendar jadwal rilis,
        kita akan mengambil data terbaru dari series penting sebagai proksi.
        """
        # Daftar series penting untuk dipantau
        important_series = {
            'FEDFUNDS': 'Suku Bunga Fed',
            'CPIAUCSL': 'Inflasi AS (CPI)',
            'GDP': 'PDB AS',
            'UNRATE': 'Tingkat Pengangguran AS',
            'PAYEMS': 'Nonfarm Payrolls',
            'DFF': 'Federal Funds Rate',
        }

        all_data = []
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d') # ambil 30 hari terakhir

        for series_id, description in important_series.items():
            df = self.get_series_data(series_id, observation_start=start_date, observation_end=end_date)
            if not df.empty:
                # Ambil data terbaru
                latest = df.iloc[-1]
                previous = df.iloc[-2] if len(df) > 1 else None
                change = (latest['value'] - previous['value']) if previous is not None else 0

                all_data.append({
                    'date': latest['date'],  # ini adalah Timestamp
                    'series_id': series_id,
                    'description': description,
                    'actual': latest['value'],
                    'previous': previous['value'] if previous is not None else None,
                    'change': change,
                    'impact': 'High' if series_id in ['FEDFUNDS', 'PAYEMS', 'CPIAUCSL'] else 'Medium'
                })
        return pd.DataFrame(all_data)

    def save_to_database(self, df: pd.DataFrame, db_path: str = 'data/saham.db'):
        """
        Menyimpan data ekonomi ke database.
        """
        if df.empty:
            logging.warning("Tidak ada data untuk disimpan.")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Buat tabel economic_data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS economic_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                series_id TEXT,
                description TEXT,
                actual REAL,
                previous REAL,
                change REAL,
                impact TEXT,
                updated_at TEXT
            )
        ''')

        # Kosongkan tabel lama (atau bisa juga update dengan logic upsert)
        cursor.execute("DELETE FROM economic_data")

        for _, row in df.iterrows():
            # Konversi date ke string jika masih Timestamp
            date_val = row['date']
            if hasattr(date_val, 'strftime'):
                date_str = date_val.strftime('%Y-%m-%d')
            else:
                date_str = str(date_val)

            cursor.execute('''
                INSERT INTO economic_data (date, series_id, description, actual, previous, change, impact, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date_str,
                row['series_id'],
                row['description'],
                row['actual'],
                row['previous'],
                row['change'],
                row['impact'],
                datetime.now().isoformat()
            ))

        conn.commit()
        conn.close()
        logging.info(f"Data ekonomi disimpan ({len(df)} series).")

    def update_economic_data(self):
        """
        Fungsi utama untuk memperbarui data ekonomi.
        """
        df = self.get_economic_calendar()
        if not df.empty:
            self.save_to_database(df)
            return True
        return False


# Singleton instance
_fetcher_instance = None

def get_fetcher():
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = EconomicFetcher()
    return _fetcher_instance