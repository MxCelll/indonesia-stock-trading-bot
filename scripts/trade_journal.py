import sqlite3
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
DB_PATH = 'data/saham.db'

def init_journal_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            entry_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            exit_date TEXT,
            exit_price REAL,
            pnl REAL,
            pnl_percent REAL,
            signal_type TEXT,
            reason TEXT,
            status TEXT DEFAULT 'open'
        )
    ''')
    conn.commit()
    conn.close()

def record_entry(symbol, entry_date, entry_price, quantity, signal_type, reason):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trade_journal
        (symbol, entry_date, entry_price, quantity, signal_type, reason, status)
        VALUES (?, ?, ?, ?, ?, ?, 'open')
    ''', (symbol, entry_date, entry_price, quantity, signal_type, reason))
    conn.commit()
    conn.close()
    logger.info(f"📝 Jurnal: Entry {symbol} dicatat.")

def record_exit(symbol, exit_date, exit_price, pnl, pnl_percent):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, entry_price, quantity FROM trade_journal
        WHERE symbol = ? AND status = 'open'
        ORDER BY entry_date ASC LIMIT 1
    ''', (symbol,))
    row = cursor.fetchone()
    if row:
        trade_id, entry_price, quantity = row
        cursor.execute('''
            UPDATE trade_journal
            SET exit_date = ?, exit_price = ?, pnl = ?, pnl_percent = ?, status = 'closed'
            WHERE id = ?
        ''', (exit_date, exit_price, pnl, pnl_percent, trade_id))
        conn.commit()
        logger.info(f"📝 Jurnal: Exit {symbol} dicatat (PnL {pnl:.2f}).")
    else:
        logger.warning(f"⚠️ Jurnal: Tidak menemukan posisi terbuka untuk {symbol}.")
    conn.close()

def get_journal_summary(period_days=7):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT COUNT(*), SUM(pnl), AVG(pnl_percent),
               SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
        FROM trade_journal
        WHERE exit_date >= ? AND status = 'closed'
    ''', (cutoff,))
    total_trades, total_pnl, avg_pnl_pct, wins = cursor.fetchone()
    total_trades = total_trades or 0
    total_pnl = total_pnl or 0.0
    avg_pnl_pct = avg_pnl_pct or 0.0
    wins = wins or 0
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    cursor.execute('''
        SELECT symbol, entry_date, entry_price, quantity FROM trade_journal
        WHERE status = 'open'
    ''')
    open_positions = cursor.fetchall()
    conn.close()
    return {
        'total_trades': total_trades,
        'total_pnl': total_pnl,
        'avg_pnl_pct': avg_pnl_pct,
        'win_rate': win_rate,
        'open_positions': open_positions
    }

def get_recent_trades(limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT symbol, entry_date, entry_price, exit_date, exit_price, pnl_percent, status
        FROM trade_journal
        ORDER BY entry_date DESC
        LIMIT ?
    ''', (limit,))
    trades = cursor.fetchall()
    conn.close()
    return trades