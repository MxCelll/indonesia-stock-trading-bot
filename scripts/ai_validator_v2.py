import time
import json
import os
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY tidak ditemukan di file .env")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

MODEL_NAME = 'deepseek-chat'
MAX_RETRIES = 3
RETRY_DELAY = 5

def validate_signal_with_ai(symbol, df_slice):
    latest = df_slice.iloc[-1]
    prev = df_slice.iloc[-2] if len(df_slice) > 1 else None

    prompt = f"""
    Anda adalah analis saham profesional untuk saham Indonesia.
    Analisis saham {symbol} berdasarkan data teknikal berikut (harian):

    Data terkini (hari ini):
    - Harga Close: {latest['Close']:.0f}
    - RSI (14): {latest['RSI']:.2f}
    - MACD: {latest['MACD']:.2f}, Signal: {latest['MACD_signal']:.2f}
    - EMA20: {latest['EMA20']:.0f}, EMA50: {latest['EMA50']:.0f}, EMA200: {latest['EMA200']:.0f}
    - Volume: {latest['Volume']:.0f} (rata-rata 20 hari: {latest['Volume_MA20']:.0f})
    - ATR: {latest['ATR']:.0f}
    - ADX: {latest['ADX']:.2f} (DI+: {latest['DI_plus']:.2f}, DI-: {latest['DI_minus']:.2f})

    Data hari sebelumnya (untuk perbandingan):
    - Harga: {prev['Close']:.0f} jika ada
    - RSI: {prev['RSI']:.2f} jika ada

    Berdasarkan data di atas, berikan opini Anda:
    1. Apakah saham ini sedang overbought, oversold, atau netral?
    2. Bagaimana tren jangka pendek (naik/turun/sideways)?
    3. Apakah Anda merekomendasikan beli, jual, atau tahan? Sertakan confidence level (0-100%).
    4. Berikan penjelasan singkat dalam Bahasa Indonesia (maks 3 kalimat).

    Format jawaban dalam JSON:
    {{
        "market_condition": "oversold/overbought/netral",
        "trend": "uptrend/downtrend/sideways",
        "recommendation": "buy/sell/hold",
        "confidence": 0-100,
        "reason": "penjelasan singkat"
    }}
    """

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            text = response.choices[0].message.content
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
            result = json.loads(text)
            return result
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"⚠️ DeepSeek error, mencoba ulang... ({attempt+2}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                return {
                    "market_condition": "unknown",
                    "trend": "unknown",
                    "recommendation": "hold",
                    "confidence": 0,
                    "reason": f"Error setelah {MAX_RETRIES} percobaan: {e}"
                }