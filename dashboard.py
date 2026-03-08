# dashboard.py
import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import time

# Konfigurasi halaman
st.set_page_config(page_title="Bot Trading Dashboard", layout="wide")
st.title("📊 Bot Trading Dashboard")

# Path database
DB_PATH = 'data/saham.db'
LOG_FILE = 'trading_bot.log'

# Inisialisasi session state
if 'last_error_check' not in st.session_state:
    st.session_state.last_error_check = datetime.now()
    st.session_state.error_count = 0

# ==================== FUNGSI HELPERS ====================
def load_journal():
    """Memuat data jurnal trading"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM trade_journal ORDER BY entry_date DESC", conn)
    conn.close()
    if not df.empty:
        df['entry_date'] = pd.to_datetime(df['entry_date'])
        df['exit_date'] = pd.to_datetime(df['exit_date'], errors='coerce')
    return df

def load_fundamental():
    """Memuat data fundamental"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM fundamental_data", conn)
    conn.close()
    return df

def load_positions():
    """Memuat posisi terbuka dari trade_journal (status='open')"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM trade_journal WHERE status='open'", conn)
    conn.close()
    return df

def load_last_logs(n=50):
    """Membaca n baris terakhir dari file log"""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    return lines[-n:]

def get_system_status():
    """Mengecek apakah bot berjalan"""
    import psutil
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and 'python' in proc.info['name'].lower() and 'main.py' in ' '.join(cmdline):
                return True
        except:
            pass
    return False

def get_agent_performance():
    """Mengambil data performa agen dari tabel agent_performance"""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM agent_performance ORDER BY date DESC LIMIT 1000", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def get_cluster_sentiment():
    """Mengambil data sentimen klaster terbaru"""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM cluster_sentiments ORDER BY updated_at DESC LIMIT 50", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def check_new_errors():
    """Memeriksa apakah ada error baru dalam 5 menit terakhir"""
    logs = load_last_logs(100)
    error_lines = [line for line in logs if 'ERROR' in line]
    now = datetime.now()
    count = 0
    for line in error_lines:
        # Asumsi format log: "2026-03-08 10:30:15,123 - ERROR - ..."
        try:
            ts_str = line[:23]  # ambil timestamp
            ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S,%f')
            if (now - ts).total_seconds() < 300:  # 5 menit
                count += 1
        except:
            continue
    return count

# ==================== SIDEBAR ====================
st.sidebar.header("🔍 Kontrol")
refresh = st.sidebar.button("🔄 Refresh Data")
auto_refresh = st.sidebar.checkbox("Auto-refresh setiap 30 detik")
if auto_refresh:
    time.sleep(30)
    st.rerun()

if 'last_refresh' not in st.session_state or refresh:
    st.session_state.last_refresh = datetime.now()

bot_running = get_system_status()
st.sidebar.info(f"Bot Status: {'🟢 Running' if bot_running else '🔴 Stopped'}")
st.sidebar.text(f"Terakhir update: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

# Notifikasi error baru
error_count = check_new_errors()
if error_count > st.session_state.error_count:
    st.session_state.error_count = error_count
    if error_count > 0:
        st.sidebar.error(f"⚠️ {error_count} error baru dalam 5 menit terakhir!")
else:
    st.sidebar.info("✅ Tidak ada error baru")

# ==================== TAB UTAMA ====================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📈 Ringkasan", "📊 Equity Curve", "📌 Posisi", "📋 Log", "🤖 Performa Agen", "📰 Sentimen"])

# ==================== TAB 1: RINGKASAN ====================
with tab1:
    st.header("Ringkasan Performa")
    col1, col2, col3, col4 = st.columns(4)
    
    df_journal = load_journal()
    closed = df_journal[df_journal['status'] == 'closed'] if not df_journal.empty else pd.DataFrame()
    
    if not closed.empty:
        total_pnl = closed['pnl'].sum()
        win_rate = (len(closed[closed['pnl'] > 0]) / len(closed)) * 100
        avg_pnl = closed['pnl'].mean()
        profit_factor = abs(closed[closed['pnl'] > 0]['pnl'].sum() / closed[closed['pnl'] < 0]['pnl'].sum()) if len(closed[closed['pnl'] < 0]) > 0 else 0
        num_trades = len(closed)
    else:
        total_pnl = win_rate = avg_pnl = profit_factor = num_trades = 0
    
    col1.metric("Total PnL", f"Rp {total_pnl:,.0f}")
    col2.metric("Win Rate", f"{win_rate:.1f}%")
    col3.metric("Rata-rata PnL", f"Rp {avg_pnl:,.0f}")
    col4.metric("Profit Factor", f"{profit_factor:.2f}")
    
    # Daftar saham yang dipantau
    st.subheader("📌 Watchlist")
    from scripts.watchlist import load_watchlist
    watchlist = load_watchlist()
    if watchlist['symbols']:
        st.write(", ".join(watchlist['symbols']))
    else:
        st.write("Watchlist kosong.")

# ==================== TAB 2: EQUITY CURVE dengan FILTER TANGGAL ====================
with tab2:
    st.header("Equity Curve (Closed Trades)")
    
    if not closed.empty:
        # Filter tanggal
        col1, col2 = st.columns(2)
        min_date = closed['exit_date'].min().date()
        max_date = closed['exit_date'].max().date()
        start_date = col1.date_input("Tanggal Mulai", min_date)
        end_date = col2.date_input("Tanggal Akhir", max_date)
        
        filtered = closed[(closed['exit_date'].dt.date >= start_date) & (closed['exit_date'].dt.date <= end_date)]
        if not filtered.empty:
            equity = filtered.sort_values('exit_date')
            equity['cum_pnl'] = equity['pnl'].cumsum()
            fig = px.line(equity, x='exit_date', y='cum_pnl', title='Akumulasi PnL',
                          labels={'exit_date': 'Tanggal', 'cum_pnl': 'PnL Kumulatif (Rp)'})
            fig.update_layout(hovermode='x unified')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data dalam rentang tanggal tersebut.")
    else:
        st.info("Belum ada closed trade.")

# ==================== TAB 3: POSISI ====================
with tab3:
    st.header("Posisi Terbuka")
    positions = load_positions()
    if not positions.empty:
        # Ambil harga terbaru dari database untuk setiap simbol
        conn = sqlite3.connect(DB_PATH)
        latest_prices = {}
        for sym in positions['symbol'].unique():
            df_price = pd.read_sql(f"SELECT Date, Close FROM saham WHERE Symbol='{sym}' ORDER BY Date DESC LIMIT 1", conn)
            if not df_price.empty:
                latest_prices[sym] = df_price.iloc[0]['Close']
        conn.close()
        
        positions['current_price'] = positions['symbol'].map(latest_prices)
        positions['unrealized_pnl'] = (positions['current_price'] - positions['entry_price']) * positions['quantity']
        positions['unrealized_pnl_pct'] = (positions['current_price'] / positions['entry_price'] - 1) * 100
        
        st.dataframe(positions[['symbol', 'entry_date', 'entry_price', 'quantity', 'current_price', 'unrealized_pnl', 'unrealized_pnl_pct']])
    else:
        st.info("Tidak ada posisi terbuka.")

# ==================== TAB 4: LOG ====================
with tab4:
    st.header("Log Terbaru (50 baris)")
    logs = load_last_logs(50)
    for line in logs:
        if 'ERROR' in line:
            st.error(line.strip())
        elif 'WARNING' in line:
            st.warning(line.strip())
        else:
            st.text(line.strip())

# ==================== TAB 5: PERFORMA AGEN ====================
with tab5:
    st.header("Performa Agen")
    df_agent = get_agent_performance()
    if not df_agent.empty:
        # Hitung metrik per agen
        df_agent['correct'] = ( (df_agent['signal'] == 1) & (df_agent['actual_return'] > 0) ) | ( (df_agent['signal'] == -1) & (df_agent['actual_return'] < 0) )
        agent_stats = df_agent.groupby('agent_name').agg(
            total_signals=('signal', 'count'),
            correct_signals=('correct', 'sum'),
            avg_confidence=('confidence', 'mean'),
            avg_return=('actual_return', 'mean')
        ).reset_index()
        agent_stats['accuracy'] = (agent_stats['correct_signals'] / agent_stats['total_signals']) * 100
        agent_stats = agent_stats.sort_values('accuracy', ascending=False)
        
        st.dataframe(agent_stats)
        
        # Grafik akurasi per agen
        fig = px.bar(agent_stats, x='agent_name', y='accuracy', title='Akurasi Agen (%)')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Belum ada data performa agen.")

# ==================== TAB 6: SENTIMEN ====================
with tab6:
    st.header("Sentimen Klaster Terkini")
    df_sent = get_cluster_sentiment()
    if not df_sent.empty:
        df_sent = df_sent.sort_values('avg_sentiment', ascending=False)
        fig = px.bar(df_sent.head(20), x='cluster_name', y='avg_sentiment', 
                     title='20 Klaster dengan Sentimen Tertinggi',
                     labels={'cluster_name': 'Klaster', 'avg_sentiment': 'Sentimen Rata-rata'})
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabel sentimen
        st.dataframe(df_sent[['cluster_name', 'symbols', 'avg_sentiment', 'article_count', 'updated_at']].head(20))
    else:
        st.info("Belum ada data sentimen klaster.")