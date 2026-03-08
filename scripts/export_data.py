# scripts/export_data.py
import sqlite3
import pandas as pd
import io

def export_saham_to_csv(symbol, db_path='data/saham.db'):
    """
    Mengekspor data saham ke format CSV dan mengembalikan bytes.
    """
    conn = sqlite3.connect(db_path)
    query = f"""
    SELECT Date, Open, High, Low, Close, Volume
    FROM saham
    WHERE Symbol = '{symbol}'
    ORDER BY Date ASC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    if df.empty:
        return None
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return output.getvalue().encode('utf-8')