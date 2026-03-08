# scripts/scraper_investing.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import logging
import sqlite3
from datetime import datetime
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)
DB_PATH = 'data/saham.db'

# Daftar User-Agent untuk rotasi
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/91.0.4472.80 Mobile/15E148 Safari/604.1'
]

# Daftar proxy gratis (contoh, sebaiknya ganti dengan proxy yang lebih stabil atau berbayar)
FREE_PROXIES = [
    'http://154.16.63.16:8080',
    'http://103.152.112.120:80',
    'http://185.199.229.156:7492',
    'http://45.61.137.100:80',
    'http://104.248.63.17:80',
    'http://188.166.56.99:80',
    # Tambahkan lebih banyak dari https://free-proxy-list.net/
]

# Variabel global untuk menyimpan Playwright dan browser
_playwright = None
_browser = None

def get_random_headers():
    """Mengembalikan headers dengan User-Agent acak."""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

def get_proxy():
    """Mengambil proxy acak dari daftar. Untuk proxy berbayar, sesuaikan formatnya."""
    proxy_url = random.choice(FREE_PROXIES)
    return {'server': proxy_url}

def get_browser(proxy=None):
    """Mendapatkan instance browser dengan proxy opsional."""
    global _playwright, _browser
    if _browser is None:
        _playwright = sync_playwright().start()
        launch_args = {
            'headless': True,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials'
            ]
        }
        if proxy:
            launch_args['proxy'] = proxy
        _browser = _playwright.chromium.launch(**launch_args)
    return _browser

def close_browser():
    """Menutup browser dan Playwright."""
    global _playwright, _browser
    if _browser:
        _browser.close()
        _browser = None
    if _playwright:
        _playwright.stop()
        _playwright = None

def fetch_with_playwright(url, timeout=60000, use_proxy=True):
    """
    Mengambil halaman menggunakan Playwright dengan anti-deteksi.
    
    Args:
        url (str): URL target.
        timeout (int): Timeout dalam milidetik.
        use_proxy (bool): Apakah menggunakan proxy acak.
    
    Returns:
        str atau None: HTML halaman jika berhasil.
    """
    # Pilih proxy jika diminta
    proxy = get_proxy() if use_proxy else None
    browser = get_browser(proxy)
    
    # Buat context dengan user-agent acak
    context = browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={'width': random.randint(1024, 1920), 'height': random.randint(768, 1080)}
    )
    page = context.new_page()
    
    # Sembunyikan webdriver
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
    """)
    
    try:
        # Navigasi dengan wait_until='domcontentloaded' agar lebih cepat
        response = page.goto(url, timeout=timeout, wait_until='domcontentloaded')
        if not response or response.status != 200:
            logger.error(f"Playwright: HTTP {response.status if response else 'No response'} for {url}")
            return None
        
        # Tunggu tabel muncul (10 detik)
        try:
            page.wait_for_selector('table.historicalTbl', timeout=10000)
        except:
            try:
                page.wait_for_selector('table.genTbl', timeout=5000)
            except:
                logger.warning(f"Tabel tidak ditemukan di {url}")
                # Ambil HTML apa adanya untuk debugging
                pass
        
        # Scroll untuk memuat semua data
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(1, 3))  # Jeda acak
        
        html = page.content()
        return html
    except Exception as e:
        logger.error(f"Playwright error untuk {url}: {e}")
        return None
    finally:
        page.close()
        context.close()

def fetch_page(url, retries=3, use_proxy=True):
    """
    Mengambil halaman dengan prioritas Playwright, fallback ke requests.
    """
    # Coba dengan Playwright
    for attempt in range(retries):
        html = fetch_with_playwright(url, use_proxy=use_proxy)
        if html:
            return html
        logger.warning(f"Playwright percobaan {attempt+1} gagal, mencoba ulang dengan proxy berbeda...")
        time.sleep(random.uniform(5, 10))
    
    # Fallback ke requests dengan proxy
    logger.warning("Playwright gagal total, fallback ke requests...")
    for attempt in range(retries):
        try:
            proxies = get_proxy() if use_proxy else None
            headers = get_random_headers()
            response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.warning(f"Requests percobaan {attempt+1}/{retries} gagal: {e}")
            time.sleep(random.uniform(5, 10))
    
    logger.error(f"Semua percobaan gagal untuk {url}")
    return None

def parse_historical_table(html):
    """
    Parse tabel historis dari halaman Investing.com.
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    table = soup.find('table', {'class': 'historicalTbl'})
    if not table:
        table = soup.find('table', {'class': 'genTbl'})
    if not table:
        logger.warning("Tabel tidak ditemukan di halaman.")
        return None
    
    rows = table.find_all('tr')
    if len(rows) < 2:
        return None
    
    data = []
    for row in rows[1:]:
        cols = row.find_all('td')
        if len(cols) >= 6:
            try:
                date = cols[0].text.strip()
                close = cols[1].text.strip().replace(',', '')
                open_price = cols[2].text.strip().replace(',', '')
                high = cols[3].text.strip().replace(',', '')
                low = cols[4].text.strip().replace(',', '')
                vol = cols[5].text.strip().replace(',', '')
                
                # Konversi volume
                if vol.endswith('K'):
                    vol = float(vol[:-1]) * 1_000
                elif vol.endswith('M'):
                    vol = float(vol[:-1]) * 1_000_000
                elif vol.endswith('B'):
                    vol = float(vol[:-1]) * 1_000_000_000
                else:
                    vol = float(vol) if vol else 0
                
                data.append({
                    'Date': date,
                    'Open': float(open_price),
                    'High': float(high),
                    'Low': float(low),
                    'Close': float(close),
                    'Volume': int(vol)
                })
            except Exception as e:
                logger.warning(f"Gagal parse baris: {e}")
                continue
    
    return data

def get_historical_data(slug, max_pages=3, use_proxy=True):
    """
    Mengambil data historis dari Investing.com.
    """
    base_url = f"https://www.investing.com/equities/{slug}-historical-data"
    all_data = []
    
    for page in range(1, max_pages + 1):
        url = f"{base_url}/{page}" if page > 1 else base_url
        
        logger.info(f"Mengambil halaman {page} dari {slug}...")
        html = fetch_page(url, use_proxy=use_proxy)
        if not html:
            break
        
        data = parse_historical_table(html)
        if not data:
            logger.info(f"Tidak ada data di halaman {page}, berhenti.")
            break
        
        all_data.extend(data)
        time.sleep(random.uniform(5, 10))  # Jeda antar halaman
    
    if not all_data:
        return None
    
    df = pd.DataFrame(all_data)
    df['Date'] = pd.to_datetime(df['Date'], format='%b %d, %Y')
    df = df.sort_values('Date').drop_duplicates(subset='Date')
    return df

def save_to_database(df, symbol):
    """Menyimpan DataFrame ke tabel saham."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
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
                symbol
            ))
        conn.commit()
        conn.close()
        logger.info(f"Data {symbol} berhasil disimpan ke database ({len(df)} baris)")
        return True
    except Exception as e:
        logger.error(f"Gagal menyimpan {symbol} ke database: {e}")
        return False