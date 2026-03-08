import requests
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)
MODEL_NAME = 'deepseek-chat'

def get_news_sentiment(symbol):
    if not NEWS_API_KEY:
        return "📰 NewsAPI key tidak ditemukan di .env"

    search_symbol = symbol.replace('.JK', '')
    url = 'https://newsapi.org/v2/everything'
    params = {
        'q': f"{search_symbol} OR saham",
        'apiKey': NEWS_API_KEY,
        'language': 'id',
        'pageSize': 10,
        'sortBy': 'publishedAt'
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data['status'] != 'ok' or data['totalResults'] == 0:
            return "📰 Tidak ada berita terkait dalam 10 berita terbaru."

        articles = data['articles']
        berita_list = []
        for a in articles:
            judul = a['title'] or ''
            deskripsi = a['description'] or ''
            sumber = a['source']['name'] or 'unknown'
            berita_list.append(f"- [{sumber}] {judul}: {deskripsi}")

        berita_gabung = '\n'.join(berita_list)

        prompt = f"""
        Berikut adalah berita terkait saham {symbol}:

        {berita_gabung}

        Analisis sentimen dari setiap berita. Untuk setiap berita, berikan label (positif/negatif/netral) dan poin penting. Kemudian berikan kesimpulan sentimen keseluruhan. Format output:

        **Analisis per Berita:**
        1. [sumber] judul: [label] - [poin penting]
        2. ...

        **Kesimpulan:** [positif/negatif/netral] - [penjelasan singkat]

        Jawab dalam Bahasa Indonesia.
        """

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content

    except requests.exceptions.Timeout:
        return "📰 Timeout saat mengambil berita."
    except Exception as e:
        return f"📰 Gagal mengambil berita: {e}"