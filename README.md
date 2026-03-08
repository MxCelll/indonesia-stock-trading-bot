# 🤖 Bot Trading Saham Indonesia

Bot Telegram untuk analisis teknikal saham Indonesia dengan dukungan AI (Gemini), fitur screener, watchlist, backtesting, dan notifikasi otomatis.

## 📋 Daftar Isi
- [Fitur](#fitur)
- [Persyaratan Sistem](#persyaratan-sistem)
- [Instalasi](#instalasi)
- [Konfigurasi](#konfigurasi)
- [Cara Menjalankan](#cara-menjalankan)
- [Perintah Telegram](#perintah-telegram)
- [Struktur Proyek](#struktur-proyek)
- [Kustomisasi](#kustomisasi)
- [Pemecahan Masalah](#pemecahan-masalah)
- [Lisensi & Disclaimer](#lisensi--disclaimer)

## 🚀 Fitur
- **Data Saham**: Impor data historis dari Investing.com (CSV) ke database SQLite.
- **Analisis Teknikal**: RSI, MACD, EMA (20,50,200), Bollinger Bands, ATR, ADX, Stochastic.
- **AI Validator**: Integrasi Gemini API untuk analisis mendalam dan sentimen berita.
- **Screener**: Filter saham berdasarkan kondisi teknikal (oversold, volume spike, golden cross, dll) dengan filter kustom.
- **Watchlist**: Pantau saham favorit dengan target/stop, lengkap dengan data real-time.
- **Multi-Timeframe Analysis**: Analisis tren di daily, weekly, monthly dengan skoring.
- **Backtesting**: Simulasi trading historis dengan grafik equity curve dan metrik.
- **Notifikasi Otomatis**: Alert setiap jam saat pasar buka untuk kondisi tertentu (support/resistance, volume spike, RSI ekstrem).
- **Laporan Mingguan**: Grafik equity curve, statistik, dan evaluasi AI.
- **Bot Telegram**: Semua perintah interaktif melalui Telegram.

## 💻 Persyaratan Sistem
- Windows 10/11 (atau OS lain dengan Python 3.11+)
- Python 3.11.x (disarankan)
- Koneksi internet stabil
- Akun Telegram (untuk bot)
- API Key Gemini (dari [Google AI Studio](https://aistudio.google.com/apikey))
- API Key NewsAPI (dari [newsapi.org](https://newsapi.org/)) – opsional untuk sentimen berita

## 📥 Instalasi

### 1. Clone atau Download Proyek
```bash
git clone https://github.com/username/bot-trading-saham.git
cd bot-trading-saham
2. Buat Virtual Environment (disarankan)
bash
python -m venv venv
venv\Scripts\activate   # Windows
3. Install Dependencies
bash
pip install -r requirements.txt
4. Siapkan File .env
Buat file .env di folder utama dengan isi:

text
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
GEMINI_API_KEY=your_gemini_api_key
NEWS_API_KEY=your_newsapi_key
⚙️ Konfigurasi
Membuat Bot Telegram
Buka Telegram, cari @BotFather.

Kirim /newbot, ikuti instruksi, dapatkan token.

Cari @userinfobot untuk mendapatkan chat ID Anda.

Mendapatkan API Key Gemini
Kunjungi Google AI Studio.

Login dengan akun Google, buat API key.

Mendapatkan API Key NewsAPI (Opsional)
Daftar di newsapi.org.

Dapatkan API key gratis.

🚀 Cara Menjalankan
Mode Manual (dengan data diimpor manual)
Download data saham dari Investing.com dalam format CSV.

Letakkan file CSV di folder data_csv/.

Jalankan impor:

bash
python scripts/import_manual.py
Jalankan bot:

bash
python main.py
Menambahkan Indeks Database (Optimasi)
Jalankan sekali untuk menambahkan indeks:

bash
python scripts/add_indexes.py
🤖 Perintah Telegram
Perintah	Deskripsi	Contoh
/start	Menyapa bot	/start
/help	Menampilkan bantuan	/help
/status	Informasi bot & database	/status
/tanya <kode> <pertanyaan>	Analisis mendalam + sentimen berita	/tanya BBCA kenapa turun?
/jelas <kode>	Analisis cepat (harga, RSI, support/resistance)	/jelas BBCA
/banding <kode1> <kode2>	Bandingkan dua saham	/banding BBCA BBRI
/top	Gainers & losers (1H, 1M, 1B)	/top
/screener [filter]	Filter saham (preset atau kustom)	/screener oversold, /screener rsi<30 volume>2x
/watchlist	Tampilkan watchlist	/watchlist
/watchlist_add <kode> [target] [stop]	Tambah ke watchlist	/watchlist_add BBCA 7500 7000
/watchlist_remove <kode>	Hapus dari watchlist	/watchlist_remove BBCA
/watchlist_target <kode> <target>	Update target	/watchlist_target BBCA 7600
/watchlist_stop <kode> <stop>	Update stop	/watchlist_stop BBCA 6900
/tf <kode>	Multi-timeframe analysis	/tf BBCA
/backtest <kode>	Simulasi backtesting	/backtest BBCA
/evaluasi	Laporan mingguan	/evaluasi
📁 Struktur Proyek
text
BotTradingSaham/
├── main.py                  # Entry point scheduler
├── .env                     # Environment variables
├── requirements.txt         # Dependencies
├── data/                    # Database & cache
├── data_csv/                # Folder untuk file CSV impor
├── scripts/                 # Modul Python
│   ├── add_indexes.py
│   ├── ai_validator_v2.py
│   ├── analisis_adaptif.py
│   ├── analisis_bulk.py
│   ├── backtest.py
│   ├── bot_utils.py
│   ├── cache_manager.py
│   ├── circuit_breaker.py
│   ├── cooldown_manager.py
│   ├── data_fetcher.py
│   ├── formatters.py
│   ├── import_manual.py
│   ├── journal.py
│   ├── market_calendar.py
│   ├── market_regime.py
│   ├── multi_tf.py
│   ├── notifier.py
│   ├── notifier_engine.py
│   ├── risk_manager.py
│   ├── screener.py
│   ├── sentiment.py
│   ├── strategies.py
│   ├── strategy_selector.py
│   ├── telegram_bot.py
│   ├── top_stocks.py
│   ├── trade_executor.py
│   ├── watchlist.py
│   └── weekly_report.py
└── scripts/__init__.py
⚙️ Kustomisasi
Mengubah Parameter Strategi
Edit file scripts/strategy_selector.py atau scripts/strategies.py untuk menyesuaikan threshold RSI, ADX, dll.

Menambah Saham Baru
Cukup download CSV dari Investing.com, letakkan di data_csv/, lalu jalankan python scripts/import_manual.py.

Mengubah Waktu Notifikasi
Edit main.py pada bagian scheduler.

🐛 Pemecahan Masalah
Error ModuleNotFoundError
Pastikan virtual environment aktif dan semua dependencies terinstall.

Error ImportError (circular import)
Periksa apakah ada modul yang saling mengimpor. Gunakan scripts/formatters.py untuk fungsi format.

Bot Tidak Merespons Telegram
Periksa token di .env dan pastikan bot sudah di-start.

Data Saham Tidak Muncul
Pastikan file CSV di data_csv/ dengan format yang benar (kolom Date, Price, Open, High, Low, Vol., Change %). Jalankan impor ulang.

Error KeyError: 'EMA20'
Pastikan data memiliki cukup baris (minimal 20) untuk menghitung EMA. Periksa scripts/multi_tf.py dan scripts/analisis_adaptif.py.

📜 Lisensi & Disclaimer
text
DISCLAIMER:
Bot ini dibuat untuk tujuan edukasi dan tidak bertanggung jawab atas kerugian finansial.
Trading saham berisiko tinggi. Konsultasikan dengan penasihat keuangan sebelum mengambil keputusan.
Penulis tidak berafiliasi dengan broker atau sekuritas manapun.