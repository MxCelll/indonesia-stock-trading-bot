import unittest
import pandas as pd
import numpy as np
import sys
import os

# Tambahkan path ke folder utama agar bisa import scripts
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from scripts.data_utils import tambah_indikator

class TestIndicators(unittest.TestCase):
    def setUp(self):
        """Membuat data dummy untuk pengujian"""
        # Buat 100 baris data harga acak
        dates = pd.date_range('2025-01-01', periods=100)
        np.random.seed(42)  # agar hasil konsisten
        self.df = pd.DataFrame({
            'Date': dates,
            'Open': np.random.randn(100).cumsum() + 100,
            'High': np.random.randn(100).cumsum() + 102,
            'Low': np.random.randn(100).cumsum() + 98,
            'Close': np.random.randn(100).cumsum() + 100,
            'Volume': np.random.randint(1000, 10000, 100)
        })
    
    def test_tambah_indikator_returns_dataframe(self):
        """Memastikan fungsi mengembalikan DataFrame"""
        result = tambah_indikator(self.df)
        self.assertIsInstance(result, pd.DataFrame)
    
    def test_tambah_indikator_adds_columns(self):
        """Memastikan kolom indikator ditambahkan"""
        result = tambah_indikator(self.df)
        expected_columns = ['RSI', 'MACD', 'MACD_signal', 'MACD_diff', 'EMA20', 'EMA50', 
                            'EMA200', 'BB_upper', 'BB_middle', 'BB_lower', 'ATR', 'ADX', 
                            'DI_plus', 'DI_minus', 'Volume_MA20']
        for col in expected_columns:
            self.assertIn(col, result.columns, f"Kolom {col} tidak ditemukan")
    
    def test_rsi_values_in_range(self):
        """Memastikan RSI berada di antara 0 dan 100"""
        result = tambah_indikator(self.df)
        rsi = result['RSI'].dropna()
        self.assertTrue((rsi >= 0).all() and (rsi <= 100).all(), "RSI di luar rentang 0-100")
    
    def test_macd_diff_consistency(self):
        """Memastikan MACD_diff = MACD - MACD_signal"""
        result = tambah_indikator(self.df)
        # Ambil baris tanpa NaN
        valid = result.dropna(subset=['MACD', 'MACD_signal', 'MACD_diff'])
        diff = valid['MACD'] - valid['MACD_signal']
        pd.testing.assert_series_equal(valid['MACD_diff'], diff, check_names=False)

if __name__ == '__main__':
    unittest.main()