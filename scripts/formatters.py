# scripts/formatters.py
import pandas as pd

def format_rupiah(angka):
    if angka is None or pd.isna(angka):
        return "N/A"
    return f"Rp {angka:,.0f}".replace(',', '.')

def format_persen(angka, desimal=2):
    if angka is None or pd.isna(angka):
        return "N/A"
    return f"{angka:+.2f}%".replace('+', '+') if angka > 0 else f"{angka:.2f}%"

def format_volume(vol):
    if vol is None or pd.isna(vol) or vol == 0:
        return "0"
    if vol > 1e9:
        return f"{vol/1e9:.2f}B"
    elif vol > 1e6:
        return f"{vol/1e6:.2f}M"
    elif vol > 1e3:
        return f"{vol/1e3:.2f}K"
    else:
        return str(vol)

def format_rsi(rsi):
    if rsi is None or pd.isna(rsi):
        return "N/A"
    if rsi < 30:
        return f"{rsi:.1f} 🟢 (oversold)"
    elif rsi > 70:
        return f"{rsi:.1f} 🔴 (overbought)"
    else:
        return f"{rsi:.1f} ⚪ (netral)"