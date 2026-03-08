# test_advanced_indicators.py
from scripts.data_utils import ambil_data_dari_db, tambah_indikator

symbol = 'BBCA.JK'
df = ambil_data_dari_db(symbol, hari=300)
df_adv = tambah_indikator(df, advanced=True)
print("Kolom baru:", df_adv.columns.tolist())
print(df_adv[['tenkan_sen', 'kijun_sen', 'senkou_span_a', 'fib_05']].tail())