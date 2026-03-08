import json
import os
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
from scripts.market_regime import detect_regime
from scripts.formatters import format_rupiah, format_persen, format_rsi, format_volume

WATCHLIST_FILE = 'data/watchlist.json'

def load_watchlist():
    default = {'symbols': []}
    if not os.path.exists(WATCHLIST_FILE):
        return default
    with open(WATCHLIST_FILE, 'r') as f:
        return json.load(f)
    try:
        with open(WATCHLIST_FILE, 'r') as f:
            data = json.load(f)
        if 'symbols' not in data: data['symbols'] = []
        if 'targets' not in data: data['targets'] = {}
        if 'stops' not in data: data['stops'] = {}
        return data
    except Exception:
        return default_data.copy()

def save_watchlist(data):
    os.makedirs('data', exist_ok=True)
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def add_to_watchlist(symbol, target=None, stop=None):
    data = load_watchlist()
    if symbol not in data['symbols']:
        data['symbols'].append(symbol)
    if target is not None:
        data['targets'][symbol] = target
    if stop is not None:
        data['stops'][symbol] = stop
    save_watchlist(data)

def remove_from_watchlist(symbol):
    data = load_watchlist()
    if symbol in data['symbols']:
        data['symbols'].remove(symbol)
    if symbol in data['targets']:
        del data['targets'][symbol]
    if symbol in data['stops']:
        del data['stops'][symbol]
    save_watchlist(data)

def update_target(symbol, target):
    data = load_watchlist()
    if symbol in data['symbols']:
        data['targets'][symbol] = target
        save_watchlist(data)
        return True
    return False

def update_stop(symbol, stop):
    data = load_watchlist()
    if symbol in data['symbols']:
        data['stops'][symbol] = stop
        save_watchlist(data)
        return True
    return False

def get_watchlist_data():
    data = load_watchlist()
    symbols = data['symbols']
    targets = data['targets']
    stops = data['stops']
    results = []
    for sym in symbols:
        df = ambil_data_dari_db(sym, hari=30)
        if df is None or len(df) < 14:
            continue
        df = tambah_indikator(df)
        latest = df.iloc[-1]
        support = df['Low'].tail(20).min()
        resistance = df['High'].tail(20).max()
        regime = detect_regime(df)
        if len(df) > 1:
            prev = df.iloc[-2]
            change_pct = (latest['Close'] - prev['Close']) / prev['Close'] * 100
        else:
            change_pct = 0.0
        volume = latest['Volume']
        vol_ma = df['Volume'].tail(20).mean()
        vol_ratio = volume / vol_ma if vol_ma > 0 else 0
        if latest['RSI'] < 30 and latest['Close'] > latest['EMA20']:
            signal = "Beli"
        elif latest['RSI'] > 70 and latest['Close'] < latest['EMA20']:
            signal = "Jual"
        else:
            signal = "Tahan"
        results.append({
            'symbol': sym,
            'price': latest['Close'],
            'change_pct': change_pct,
            'rsi': latest['RSI'],
            'volume': volume,
            'vol_ratio': vol_ratio,
            'support': support,
            'resistance': resistance,
            'regime': regime,
            'signal': signal,
            'target': targets.get(sym),
            'stop': stops.get(sym)
        })
    return results

def format_watchlist():
    data = get_watchlist_data()
    if not data:
        return "📋 *Watchlist*\n\nKosong. Tambahkan dengan /watchlist_add <kode> [target] [stop]"
    lines = ["📋 *Watchlist*\n"]
    for item in data:
        change_emoji = "📈" if item['change_pct'] > 0 else "📉" if item['change_pct'] < 0 else "➡️"
        vol_emoji = "🔥" if item['vol_ratio'] > 2 else "📊" if item['vol_ratio'] > 1.5 else "💧"
        line = (
            f"• *{item['symbol']}*\n"
            f"  {change_emoji} Harga: {format_rupiah(item['price'])} ({format_persen(item['change_pct'])})\n"
            f"  📊 RSI: {format_rsi(item['rsi'])} | Sinyal: {item['signal']}\n"
            f"  {vol_emoji} Volume: {format_volume(item['volume'])} ({item['vol_ratio']:.1f}x MA)\n"
            f"  📈 Regime: {item['regime']}\n"
            f"  🔝 Resistance: {format_rupiah(item['resistance'])} | 🔻 Support: {format_rupiah(item['support'])}\n"
        )
        if item['target']:
            line += f"  🎯 Target: {format_rupiah(item['target'])}\n"
        if item['stop']:
            line += f"  🛑 Stop: {format_rupiah(item['stop'])}\n"
        lines.append(line + "\n")
    return '\n'.join(lines)