# scripts/weekly_report.py
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import io
import logging
from datetime import datetime, timedelta
from openai import OpenAI
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)
MODEL_NAME = 'deepseek-chat'

def generate_report():
    conn = sqlite3.connect('data/saham.db')
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    query = f"""
    SELECT * FROM trades 
    WHERE exit_date IS NOT NULL AND exit_date >= '{one_week_ago}'
    ORDER BY exit_date
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        return None, "📭 Tidak ada transaksi dalam seminggu terakhir."
    
    total_pnl = df['pnl'].sum()
    win_trades = df[df['pnl'] > 0]
    loss_trades = df[df['pnl'] <= 0]
    win_rate = len(win_trades) / len(df) * 100 if len(df) > 0 else 0
    avg_win = win_trades['pnl'].mean() if not win_trades.empty else 0
    avg_loss = loss_trades['pnl'].mean() if not loss_trades.empty else 0
    profit_factor = abs(win_trades['pnl'].sum() / loss_trades['pnl'].sum()) if not loss_trades.empty and loss_trades['pnl'].sum() != 0 else float('inf')
    
    summary = f"""📊 LAPORAN MINGGUAN ({one_week_ago} - sekarang)
Total Transaksi: {len(df)}
Total PnL: Rp {total_pnl:,.0f}
Win Rate: {win_rate:.1f}%
Rata-rata Win: Rp {avg_win:,.0f}
Rata-rata Loss: Rp {avg_loss:,.0f}
Profit Factor: {profit_factor:.2f}
    """
    
    df['cumulative'] = df['pnl'].cumsum()
    plt.figure(figsize=(10,5))
    plt.plot(pd.to_datetime(df['exit_date']), df['cumulative'], marker='o', linestyle='-')
    plt.title('Equity Curve Mingguan')
    plt.xlabel('Tanggal')
    plt.ylabel('Akumulasi PnL (Rp)')
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf, summary

def get_ai_evaluation(summary_text, trades_df):
    if trades_df.empty:
        return "Tidak ada data untuk dievaluasi."
    trades_sample = trades_df[['symbol', 'entry_date', 'exit_date', 'pnl_percent']].tail(10)
    prompt = f"""
    Anda adalah mentor trading profesional. Berikut laporan mingguan:
    {summary_text}
    Data transaksi (10 terakhir):
    {trades_sample.to_string(index=False)}
    Analisis singkat dalam Bahasa Indonesia, sebut pola kesalahan dan saran perbaikan (maks 5 kalimat).
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Gagal evaluasi AI: {e}")
        return f"Gagal evaluasi AI: {e}"

async def send_weekly_report():
    # Lazy import untuk menghindari circular import
    from scripts.telegram_bot import send_photo, send_message
    
    img_buffer, summary = generate_report()
    if img_buffer:
        conn = sqlite3.connect('data/saham.db')
        one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        query = f"SELECT * FROM trades WHERE exit_date >= '{one_week_ago}'"
        df = pd.read_sql(query, conn)
        conn.close()
        if not df.empty:
            ai_eval = get_ai_evaluation(summary, df)
            caption = summary + "\n\n🤖 Evaluasi AI:\n" + ai_eval
        else:
            caption = summary
        await send_photo(img_buffer, caption=caption)
    else:
        await send_message(summary)