import sqlite3
import pandas as pd
from scripts.analisis_adaptif import ambil_data_dari_db, tambah_indikator, sinyal_dasar
from scripts.market_regime import detect_regime
from scripts.strategy_selector import get_signal
from scripts.ai_validator_v2 import validate_signal_with_ai
from scripts.data_utils import get_all_symbols

def analisis_single(symbol):
    df = ambil_data_dari_db(symbol)
    if df is None or len(df) < 30:
        return f"❌ {symbol}: Data tidak cukup"
    df = tambah_indikator(df)
    latest = df.iloc[-1]
    regime = detect_regime(df)
    sig, reason, strategy = get_signal(symbol, df)
    if sig == 1:
        sinyal = "🔴 BELI"
    elif sig == -1:
        sinyal = "🔴 JUAL"
    else:
        sinyal = "⚪ Tahan"
    ai_opinion = ""
    df_10 = df.iloc[-10:]
    ai_result = validate_signal_with_ai(symbol, df_10)
    if ai_result and 'recommendation' in ai_result:
        ai_opinion = f"AI: {ai_result['recommendation']} (conf {ai_result.get('confidence',0)}%)"
    output = f"""
📌 *{symbol}* | Harga: {latest['Close']:.0f} | RSI: {latest['RSI']:.1f}
📈 Regime: {regime} | {sinyal}
{ai_opinion}
"""
    return output

def analisis_bulk(symbols, include_ai=False):
    results = [analisis_single(sym) for sym in symbols]
    header = f"📊 *Analisis Bulk ({len(symbols)} saham)*\n"
    return header + "\n".join(results)