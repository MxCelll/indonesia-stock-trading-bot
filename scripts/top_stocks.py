import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from scripts.formatters import format_rupiah, format_persen

def get_top_stocks():
    conn = sqlite3.connect('data/saham.db')
    query = "SELECT Date, Symbol, Close FROM saham WHERE Date >= date('now', '-60 days') ORDER BY Date"
    df = pd.read_sql(query, conn)
    conn.close()
    if df.empty:
        return None
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])
    df = df[df['Close'] > 0].copy()
    latest_date = df['Date'].max()
    today = latest_date

    def get_nearest_price(symbol_data, target_date):
        mask = symbol_data['Date'] <= target_date
        subset = symbol_data[mask]
        return subset.iloc[-1]['Close'] if not subset.empty else None

    result = {}
    for symbol in df['Symbol'].unique():
        symbol_data = df[df['Symbol'] == symbol].sort_values('Date')
        if len(symbol_data) < 2:
            continue
        latest = symbol_data.iloc[-1]
        latest_price = latest['Close']
        one_day_ago = latest_date - timedelta(days=1)
        one_week_ago = latest_date - timedelta(days=7)
        one_month_ago = latest_date - relativedelta(months=1)
        day_price = get_nearest_price(symbol_data, one_day_ago)
        week_price = get_nearest_price(symbol_data, one_week_ago)
        month_price = get_nearest_price(symbol_data, one_month_ago)
        result[symbol] = {
            'latest_price': latest_price,
            'latest_date': latest['Date'],
            'day_change': ((latest_price - day_price) / day_price * 100) if day_price else None,
            'week_change': ((latest_price - week_price) / week_price * 100) if week_price else None,
            'month_change': ((latest_price - month_price) / month_price * 100) if month_price else None
        }
    return result

def format_top_stocks():
    data = get_top_stocks()
    if not data:
        return "📈 *Top Gainers & Losers*\n\nTidak ada data saham yang valid."
    valid_data = {k: v for k, v in data.items() if v['latest_price'] > 0}
    day_changes = [(s, v['day_change'], v['latest_price']) for s, v in valid_data.items() if v['day_change'] is not None]
    week_changes = [(s, v['week_change'], v['latest_price']) for s, v in valid_data.items() if v['week_change'] is not None]
    month_changes = [(s, v['month_change'], v['latest_price']) for s, v in valid_data.items() if v['month_change'] is not None]

    day_gainers = sorted([x for x in day_changes if x[1] > 0], key=lambda x: x[1], reverse=True)[:5]
    day_losers = sorted([x for x in day_changes if x[1] < 0], key=lambda x: x[1])[:5]
    week_gainers = sorted([x for x in week_changes if x[1] > 0], key=lambda x: x[1], reverse=True)[:5]
    week_losers = sorted([x for x in week_changes if x[1] < 0], key=lambda x: x[1])[:5]
    month_gainers = sorted([x for x in month_changes if x[1] > 0], key=lambda x: x[1], reverse=True)[:5]
    month_losers = sorted([x for x in month_changes if x[1] < 0], key=lambda x: x[1])[:5]

    sample = next(iter(valid_data))
    latest_date = valid_data[sample]['latest_date'].strftime('%d %b %Y')

    text = f"📈 *Top Gainers & Losers* (per {latest_date})\n\n"
    text += "*🔹 1 Hari*\n"
    if day_gainers:
        text += "📈 *Gainers:*\n"
        for i, (s, chg, p) in enumerate(day_gainers, 1):
            text += f"{i}. {s}: {format_persen(chg)} → {format_rupiah(p)}\n"
    if day_losers:
        text += "📉 *Losers:*\n"
        for i, (s, chg, p) in enumerate(day_losers, 1):
            text += f"{i}. {s}: {format_persen(chg)} → {format_rupiah(p)}\n"
    if not day_gainers and not day_losers:
        text += "_Tidak ada data_\n"

    text += "\n*🔹 1 Minggu*\n"
    if week_gainers:
        text += "📈 *Gainers:*\n"
        for i, (s, chg, p) in enumerate(week_gainers, 1):
            text += f"{i}. {s}: {format_persen(chg)} → {format_rupiah(p)}\n"
    if week_losers:
        text += "📉 *Losers:*\n"
        for i, (s, chg, p) in enumerate(week_losers, 1):
            text += f"{i}. {s}: {format_persen(chg)} → {format_rupiah(p)}\n"
    if not week_gainers and not week_losers:
        text += "_Tidak ada data_\n"

    text += "\n*🔹 1 Bulan*\n"
    if month_gainers:
        text += "📈 *Gainers:*\n"
        for i, (s, chg, p) in enumerate(month_gainers, 1):
            text += f"{i}. {s}: {format_persen(chg)} → {format_rupiah(p)}\n"
    if month_losers:
        text += "📉 *Losers:*\n"
        for i, (s, chg, p) in enumerate(month_losers, 1):
            text += f"{i}. {s}: {format_persen(chg)} → {format_rupiah(p)}\n"
    if not month_gainers and not month_losers:
        text += "_Tidak ada data_\n"

    return text