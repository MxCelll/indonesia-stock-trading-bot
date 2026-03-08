import sqlite3
import pandas as pd
import ta
from scripts.data_utils import ambil_data_dari_db
from scripts.formatters import format_rupiah

def resample_tf(df, tf='W'):
    """
    Resample data harian ke timeframe yang diinginkan.
    tf: 'W' (weekly), 'M' (monthly)
    """
    if df is None or df.empty:
        return None
    df = df.set_index('Date')
    ohlc_dict = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }
    df_tf = df.resample(tf).agg(ohlc_dict).dropna()
    df_tf.reset_index(inplace=True)
    return df_tf

def add_indicators_tf(df):
    """
    Menambahkan indikator untuk dataframe timeframe tertentu.
    Jika data kurang, kolom indikator diisi NaN.
    """
    if df is None or df.empty:
        return df
    required = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not all(col in df.columns for col in required):
        return df
    if len(df) >= 20:
        df['EMA20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()
    else:
        df['EMA20'] = float('nan')
    if len(df) >= 14:
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    else:
        df['RSI'] = float('nan')
    if len(df) >= 26:
        macd = ta.trend.MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
    else:
        df['MACD'] = float('nan')
        df['MACD_signal'] = float('nan')
    if len(df) >= 14:
        try:
            adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=14)
            df['ADX'] = adx.adx()
            df['DI_plus'] = adx.adx_pos()
            df['DI_minus'] = adx.adx_neg()
        except Exception:
            df['ADX'] = float('nan')
            df['DI_plus'] = float('nan')
            df['DI_minus'] = float('nan')
    else:
        df['ADX'] = float('nan')
        df['DI_plus'] = float('nan')
        df['DI_minus'] = float('nan')
    return df

def get_tf_analysis_v2(symbol, target_direction='buy'):
    """
    Menganalisis multi-timeframe dengan skor dan rekomendasi.
    target_direction: 'buy' atau 'sell' (untuk menghitung skor).
    Mengembalikan dict dengan skor per timeframe, total skor, dan rekomendasi.
    """
    df_raw = ambil_data_dari_db(symbol, hari=300)
    if df_raw is None or len(df_raw) < 50:
        return None, "Data harian tidak cukup (minimal 50 hari)"

    df_weekly = resample_tf(df_raw, 'W')
    df_monthly = resample_tf(df_raw, 'ME')

    df_daily = add_indicators_tf(df_raw.copy())
    if df_weekly is not None:
        df_weekly = add_indicators_tf(df_weekly)
    if df_monthly is not None:
        df_monthly = add_indicators_tf(df_monthly)

    latest_d = df_daily.iloc[-1] if df_daily is not None and len(df_daily) > 0 else None
    latest_w = df_weekly.iloc[-1] if df_weekly is not None and len(df_weekly) > 0 else None
    latest_m = df_monthly.iloc[-1] if df_monthly is not None and len(df_monthly) > 0 else None

    if latest_d is None:
        return None, "Tidak ada data harian"

    def score_timeframe(latest, target_dir):
        if latest is None:
            return 0, "Data tidak cukup"
        score = 0
        reasons = []
        if 'EMA20' in latest and pd.notna(latest['EMA20']):
            if latest['Close'] > latest['EMA20']:
                if target_dir == 'buy':
                    score += 30
                    reasons.append(f"Harga di atas EMA20 (+30)")
                else:
                    score -= 30
                    reasons.append(f"Harga di atas EMA20 (-30)")
            else:
                if target_dir == 'sell':
                    score += 30
                    reasons.append(f"Harga di bawah EMA20 (+30)")
                else:
                    score -= 30
                    reasons.append(f"Harga di bawah EMA20 (-30)")
        else:
            reasons.append("EMA20 tidak tersedia")

        if 'RSI' in latest and pd.notna(latest['RSI']):
            rsi = latest['RSI']
            if target_dir == 'buy':
                if rsi < 30:
                    score += 20
                    reasons.append(f"RSI oversold ({rsi:.1f}) (+20)")
                elif rsi > 70:
                    score -= 20
                    reasons.append(f"RSI overbought ({rsi:.1f}) (-20)")
                else:
                    score += 10
                    reasons.append(f"RSI netral ({rsi:.1f}) (+10)")
            else:
                if rsi > 70:
                    score += 20
                    reasons.append(f"RSI overbought ({rsi:.1f}) (+20)")
                elif rsi < 30:
                    score -= 20
                    reasons.append(f"RSI oversold ({rsi:.1f}) (-20)")
                else:
                    score += 10
                    reasons.append(f"RSI netral ({rsi:.1f}) (+10)")
        else:
            reasons.append("RSI tidak tersedia")

        if ('MACD' in latest and 'MACD_signal' in latest and
            pd.notna(latest['MACD']) and pd.notna(latest['MACD_signal'])):
            if latest['MACD'] > latest['MACD_signal']:
                if target_dir == 'buy':
                    score += 20
                    reasons.append("MACD bullish (+20)")
                else:
                    score -= 20
                    reasons.append("MACD bullish (-20)")
            else:
                if target_dir == 'sell':
                    score += 20
                    reasons.append("MACD bearish (+20)")
                else:
                    score -= 20
                    reasons.append("MACD bearish (-20)")
        else:
            reasons.append("MACD tidak tersedia")

        if 'ADX' in latest and pd.notna(latest['ADX']):
            adx = latest['ADX']
            if adx > 25:
                di_plus = latest.get('DI_plus', 0) if pd.notna(latest.get('DI_plus')) else 0
                di_minus = latest.get('DI_minus', 0) if pd.notna(latest.get('DI_minus')) else 0
                if target_dir == 'buy' and di_plus > di_minus:
                    score += 30
                    reasons.append(f"Tren kuat ({adx:.1f}) dengan DI+ > DI- (+30)")
                elif target_dir == 'sell' and di_minus > di_plus:
                    score += 30
                    reasons.append(f"Tren kuat ({adx:.1f}) dengan DI- > DI+ (+30)")
                else:
                    score += 15
                    reasons.append(f"Tren kuat tapi arah berbeda (+15)")
            else:
                score += 5
                reasons.append(f"Tren lemah ({adx:.1f}) (+5)")
        else:
            reasons.append("ADX tidak tersedia")

        score = max(-100, min(100, score))
        return score, "; ".join(reasons)

    score_d, reason_d = score_timeframe(latest_d, target_direction)
    score_w, reason_w = score_timeframe(latest_w, target_direction) if latest_w is not None else (0, "Data weekly tidak cukup")
    score_m, reason_m = score_timeframe(latest_m, target_direction) if latest_m is not None else (0, "Data monthly tidak cukup")

    # Bobot: daily 40%, weekly 35%, monthly 25%
    total_score = (score_d * 0.4) + (score_w * 0.35) + (score_m * 0.25)

    if total_score >= 70:
        rekomendasi = f"🚀 SANGAT BULLISH (Skor {total_score:.1f})"
    elif total_score >= 50:
        rekomendasi = f"📈 BULLISH (Skor {total_score:.1f})"
    elif total_score >= 30:
        rekomendasi = f"↗️ CENDERUNG BULLISH (Skor {total_score:.1f})"
    elif total_score <= -70:
        rekomendasi = f"💥 SANGAT BEARISH (Skor {total_score:.1f})"
    elif total_score <= -50:
        rekomendasi = f"📉 BEARISH (Skor {total_score:.1f})"
    elif total_score <= -30:
        rekomendasi = f"↘️ CENDERUNG BEARISH (Skor {total_score:.1f})"
    else:
        rekomendasi = f"➡️ NETRAL (Skor {total_score:.1f})"

    return {
        'symbol': symbol,
        'target_direction': target_direction,
        'total_score': round(total_score, 1),
        'rekomendasi': rekomendasi,
        'daily': {
            'score': score_d,
            'reason': reason_d,
            'price': latest_d['Close'],
            'adx': latest_d.get('ADX') if 'ADX' in latest_d else None,
            'rsi': latest_d.get('RSI') if 'RSI' in latest_d else None,
            'ema20': latest_d.get('EMA20') if 'EMA20' in latest_d else None
        },
        'weekly': {
            'score': score_w,
            'reason': reason_w,
            'price': latest_w['Close'] if latest_w is not None else None,
            'adx': latest_w.get('ADX') if latest_w is not None and 'ADX' in latest_w else None,
            'rsi': latest_w.get('RSI') if latest_w is not None and 'RSI' in latest_w else None,
            'ema20': latest_w.get('EMA20') if latest_w is not None and 'EMA20' in latest_w else None
        } if latest_w is not None else None,
        'monthly': {
            'score': score_m,
            'reason': reason_m,
            'price': latest_m['Close'] if latest_m is not None else None,
            'adx': latest_m.get('ADX') if latest_m is not None and 'ADX' in latest_m else None,
            'rsi': latest_m.get('RSI') if latest_m is not None and 'RSI' in latest_m else None,
            'ema20': latest_m.get('EMA20') if latest_m is not None and 'EMA20' in latest_m else None
        } if latest_m is not None else None
    }, None

def format_tf_analysis_v2(result):
    if result is None:
        return "❌ Analisis gagal."
    lines = [
        f"📊 *Multi-Timeframe Analysis: {result['symbol']}*",
        f"🎯 Arah yang dianalisis: **{result['target_direction'].upper()}**",
        f"📈 *Total Skor: {result['total_score']}*",
        f"💡 Rekomendasi: {result['rekomendasi']}\n"
    ]

    d = result['daily']
    adx_d = f" (ADX {d['adx']:.1f})" if d['adx'] and pd.notna(d['adx']) else ""
    rsi_d = f" | RSI: {d['rsi']:.1f}" if d['rsi'] and pd.notna(d['rsi']) else ""
    ema_d = f" | EMA20: {format_rupiah(d['ema20'])}" if d['ema20'] and pd.notna(d['ema20']) else ""
    lines.append(f"📅 *Daily*: Skor {d['score']}{adx_d}")
    lines.append(f"   {d['reason']}")
    lines.append(f"   Harga: {format_rupiah(d['price'])}{rsi_d}{ema_d}\n")

    w = result.get('weekly')
    if w is not None:
        adx_w = f" (ADX {w['adx']:.1f})" if w['adx'] and pd.notna(w['adx']) else ""
        rsi_w = f" | RSI: {w['rsi']:.1f}" if w['rsi'] and pd.notna(w['rsi']) else ""
        ema_w = f" | EMA20: {format_rupiah(w['ema20'])}" if w['ema20'] and pd.notna(w['ema20']) else ""
        lines.append(f"📆 *Weekly*: Skor {w['score']}{adx_w}")
        lines.append(f"   {w['reason']}")
        lines.append(f"   Harga: {format_rupiah(w['price'])}{rsi_w}{ema_w}\n")
    else:
        lines.append("📆 *Weekly*: Data tidak cukup\n")

    m = result.get('monthly')
    if m is not None:
        adx_m = f" (ADX {m['adx']:.1f})" if m['adx'] and pd.notna(m['adx']) else ""
        rsi_m = f" | RSI: {m['rsi']:.1f}" if m['rsi'] and pd.notna(m['rsi']) else ""
        ema_m = f" | EMA20: {format_rupiah(m['ema20'])}" if m['ema20'] and pd.notna(m['ema20']) else ""
        lines.append(f"🗓️ *Monthly*: Skor {m['score']}{adx_m}")
        lines.append(f"   {m['reason']}")
        lines.append(f"   Harga: {format_rupiah(m['price'])}{rsi_m}{ema_m}\n")
    else:
        lines.append("🗓️ *Monthly*: Data tidak cukup\n")

    return '\n'.join(lines)