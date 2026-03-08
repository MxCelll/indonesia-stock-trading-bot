# scripts/analyze_strategies.py
import sqlite3
import pandas as pd
import json
import logging
from datetime import datetime

# Setup logger
logger = logging.getLogger(__name__)

def analyze_strategies(symbol=None, min_trades=3, top_n=5, sort_by='total_return'):
    """
    Menganalisis strategi dari tabel strategy_experiments.
    
    Parameters:
    symbol: jika None, analisis semua simbol; jika diberikan, filter berdasarkan simbol.
    min_trades: jumlah trade minimal agar dianggap signifikan.
    top_n: jumlah strategi terbaik yang ditampilkan.
    sort_by: kolom untuk sorting ('total_return', 'profit_factor', 'win_rate', 'sharpe')
    """
    conn = sqlite3.connect('data/saham.db')
    
    query = "SELECT * FROM strategy_experiments"
    if symbol:
        query += f" WHERE symbol = '{symbol}'"
    query += " ORDER BY created_at DESC"
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        logger.warning("Tidak ada data eksperimen.")
        return
    
    # Filter berdasarkan minimal jumlah trade
    df = df[df['num_trades'] >= min_trades].copy()
    if df.empty:
        logger.info(f"Tidak ada strategi dengan minimal {min_trades} trade.")
        return
    
    # Urutkan berdasarkan kolom yang dipilih
    if sort_by in df.columns:
        df_sorted = df.sort_values(sort_by, ascending=False).head(top_n)
    else:
        logger.warning(f"Kolom {sort_by} tidak ditemukan, gunakan default 'total_return'.")
        df_sorted = df.sort_values('total_return', ascending=False).head(top_n)
    
    # Tampilkan hasil (gunakan logger, bukan print)
    logger.info("\n" + "="*80)
    logger.info(f"TOP {top_n} STRATEGI BERDASARKAN {sort_by.upper()} (min {min_trades} trades)")
    logger.info("="*80)
    for idx, row in df_sorted.iterrows():
        logger.info(f"\n📊 Strategi: {row['strategy_name']} (ID: {row['id']})")
        logger.info(f"   Simbol: {row['symbol']}")
        logger.info(f"   Total Return: {row['total_return']:.2f}%")
        logger.info(f"   Win Rate: {row['win_rate']:.1f}%")
        logger.info(f"   Profit Factor: {row['profit_factor']:.2f}")
        logger.info(f"   Max Drawdown: {row['max_drawdown']:.2f}%")
        logger.info(f"   Sharpe Ratio: {row['sharpe']:.2f}")
        logger.info(f"   Jumlah Trade: {row['num_trades']}")
        logger.info(f"   Dibuat: {row['created_at']}")
        
        # Tampilkan parameter strategi (JSON)
        try:
            params = json.loads(row['parameters'])
            logger.info(f"   Parameter: {json.dumps(params, indent=2)}")
        except:
            logger.info(f"   Parameter: (tidak dapat diparse)")
    
    # Opsi untuk menyimpan strategi terbaik ke file
    # Input tidak bisa diganti logging, tetap menggunakan input
    save = input("\nSimpan strategi terbaik ke file? (y/n): ").lower()
    if save == 'y':
        filename = f"best_strategies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        # Simpan semua top_n strategi
        output = df_sorted[['symbol', 'strategy_name', 'parameters', 'total_return', 'win_rate', 'profit_factor', 'max_drawdown', 'sharpe', 'num_trades']].to_dict(orient='records')
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        logger.info(f"Strategi terbaik disimpan ke {filename}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Analisis strategi dari database.')
    parser.add_argument('--symbol', type=str, help='Filter berdasarkan simbol (misal BBCA.JK)')
    parser.add_argument('--min-trades', type=int, default=3, help='Minimal jumlah trade')
    parser.add_argument('--top-n', type=int, default=5, help='Jumlah strategi terbaik')
    parser.add_argument('--sort-by', type=str, default='total_return', help='Kolom sorting (total_return, profit_factor, win_rate, sharpe)')
    args = parser.parse_args()
    
    analyze_strategies(symbol=args.symbol, min_trades=args.min_trades, top_n=args.top_n, sort_by=args.sort_by)