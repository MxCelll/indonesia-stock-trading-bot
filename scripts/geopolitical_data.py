# scripts/geopolitical_data.py
import requests
import pandas as pd
from datetime import datetime

class GeopoliticalDataFetcher:
    def __init__(self):
        self.gpr_url = "https://www.policyuncertainty.com/media/Global_GPR_Data.csv"
        self.vix_ticker = "^VIX"  # via yfinance
    
    def get_gpr_index(self, country="Indonesia"):
        """Mengambil Geopolitical Risk Index untuk Indonesia"""
        # GPR index tersedia per negara, termasuk Indonesia
        df = pd.read_csv(self.gpr_url)
        indonesia_gpr = df[df['Country'] == country]
        return indonesia_gpr['GPR'].iloc[-1]  # nilai terkini