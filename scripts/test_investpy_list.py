# test_investpy_list.py
import investpy

try:
    print("Mencoba mengambil daftar saham Indonesia dari investpy...")
    stocks = investpy.get_stocks_list(country='indonesia')
    print(f"\n✅ Berhasil! Ditemukan {len(stocks)} saham.")
    print("Contoh 10 saham pertama:")
    print(stocks[:10])
    
    # Simpan ke file untuk referensi
    with open('data/all_stocks_investpy.txt', 'w') as f:
        for s in stocks:
            f.write(s + '\n')
    print("\nDaftar lengkap disimpan di data/all_stocks_investpy.txt")
    
except Exception as e:
    print(f"\n❌ Gagal: {e}")
    print("\nKemungkinan investpy sedang bermasalah (error 403).")