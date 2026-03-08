# scripts/economic_indonesia.py
import requests
import sqlite3
import pandas as pd
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class IndonesiaEconomicFetcher:
    """
    Fetcher untuk data ekonomi Indonesia dari World Bank API.
    """
    
    # Daftar indikator penting dari World Bank untuk Indonesia
    INDICATORS = {
        'NY.GDP.MKTP.CD': 'GDP (US$)',
        'FP.CPI.TOTL.ZG': 'Inflasi (CPI annual %)',
        'SL.UEM.TOTL.ZS': 'Tingkat Pengangguran (% total angkatan kerja)',
        'SP.POP.TOTL': 'Total Populasi',
        'NV.AGR.TOTL.ZS': 'Pertanian (% GDP)',
        'NV.IND.TOTL.ZS': 'Industri (% GDP)',
        'NV.SRV.TOTL.ZS': 'Jasa (% GDP)',
    }
    
    BASE_URL = "http://api.worldbank.org/v2/country/id/indicator"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_indicator_data(self, indicator_code: str, years: int = 5) -> pd.DataFrame:
        """
        Mengambil data untuk satu indikator dari World Bank API.
        years: jumlah tahun terakhir yang diambil (default 5).
        """
        url = f"{self.BASE_URL}/{indicator_code}"
        params = {
            'format': 'json',
            'per_page': years,
            'date': f"2000:{datetime.now().year}"  # ambil dari tahun 2000 sampai sekarang
        }
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code != 200:
                logging.error(f"Gagal mengambil {indicator_code}: HTTP {response.status_code}")
                return pd.DataFrame()
            
            data = response.json()
            if len(data) < 2:
                return pd.DataFrame()
            
            # Data berada di index 1, dengan format [{'date': '2023', 'value': 12345}, ...]
            records = []
            for entry in data[1]:
                if entry['value'] is not None:
                    records.append({
                        'date': entry['date'],
                        'indicator': indicator_code,
                        'description': self.INDICATORS.get(indicator_code, indicator_code),
                        'value': entry['value']
                    })
            
            df = pd.DataFrame(records)
            df['updated_at'] = datetime.now().isoformat()
            return df
            
        except Exception as e:
            logging.error(f"Error mengambil {indicator_code}: {e}")
            return pd.DataFrame()
    
    def get_all_indicators(self, years: int = 5) -> pd.DataFrame:
        """
        Mengambil semua indikator yang didefinisikan.
        """
        all_dfs = []
        for code in self.INDICATORS.keys():
            df = self.get_indicator_data(code, years)
            if not df.empty:
                all_dfs.append(df)
        
        if all_dfs:
            return pd.concat(all_dfs, ignore_index=True)
        else:
            return pd.DataFrame()
    
    def save_to_database(self, df: pd.DataFrame, db_path: str = 'data/saham.db'):
        """
        Menyimpan data ekonomi Indonesia ke database.
        """
        if df.empty:
            logging.warning("Tidak ada data ekonomi Indonesia untuk disimpan.")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS economic_indonesia_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                indicator TEXT,
                description TEXT,
                value REAL,
                updated_at TEXT
            )
        ''')
        
        # Hapus data lama (atau bisa di-merge, tapi untuk sederhana hapus semua)
        cursor.execute("DELETE FROM economic_indonesia_data")
        
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT INTO economic_indonesia_data (date, indicator, description, value, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                row['date'],
                row['indicator'],
                row['description'],
                row['value'],
                row['updated_at']
            ))
        
        conn.commit()
        conn.close()
        logging.info(f"Data ekonomi Indonesia disimpan ({len(df)} baris).")
    
    def update_economic_data(self, years: int = 5):
        """
        Fungsi utama untuk update data ekonomi Indonesia.
        """
        df = self.get_all_indicators(years)
        if not df.empty:
            self.save_to_database(df)
            return True
        return False


class IndonesiaHolidayFetcher:
    """
    Fetcher untuk hari libur nasional Indonesia menggunakan Nager.Date API.
    Sumber: https://date.nager.at
    """
    
    API_URL = "https://date.nager.at/api/v3/publicholidays"
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_holidays(self, year: int = None) -> pd.DataFrame:
        """
        Mengambil hari libur nasional untuk tahun tertentu.
        Jika year tidak diberikan, ambil tahun sekarang dan tahun depan.
        """
        if year is None:
            years = [datetime.now().year, datetime.now().year + 1]
        else:
            years = [year]
        
        all_holidays = []
        for y in years:
            url = f"{self.API_URL}/{y}/id"
            try:
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for h in data:
                        all_holidays.append({
                            'date': h['date'],
                            'local_name': h['localName'],
                            'name': h['name'],
                            'country_code': 'ID'
                        })
                else:
                    logging.error(f"Gagal mengambil libur tahun {y}: HTTP {response.status_code}")
            except Exception as e:
                logging.error(f"Error mengambil libur tahun {y}: {e}")
        
        return pd.DataFrame(all_holidays)
    
    def save_to_database(self, df: pd.DataFrame, db_path: str = 'data/saham.db'):
        """
        Menyimpan data hari libur ke database.
        """
        if df.empty:
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS indonesia_holidays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                local_name TEXT,
                name TEXT,
                country_code TEXT
            )
        ''')
        
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO indonesia_holidays (date, local_name, name, country_code)
                VALUES (?, ?, ?, ?)
            ''', (
                row['date'],
                row['local_name'],
                row['name'],
                row['country_code']
            ))
        
        conn.commit()
        conn.close()
        logging.info(f"Data libur nasional disimpan ({len(df)} hari).")
    
    def update_holidays(self):
        """
        Update data libur untuk tahun sekarang dan tahun depan.
        """
        df = self.get_holidays()
        if not df.empty:
            self.save_to_database(df)
            return True
        return False


# Singleton instances
_econ_fetcher = None
_holiday_fetcher = None

def get_econ_fetcher():
    global _econ_fetcher
    if _econ_fetcher is None:
        _econ_fetcher = IndonesiaEconomicFetcher()
    return _econ_fetcher

def get_holiday_fetcher():
    global _holiday_fetcher
    if _holiday_fetcher is None:
        _holiday_fetcher = IndonesiaHolidayFetcher()
    return _holiday_fetcher