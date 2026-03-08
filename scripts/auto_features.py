# scripts/auto_features.py
import featuretools as ft
import pandas as pd
import numpy as np
from scripts.data_utils import ambil_data_dari_db, tambah_indikator

def generate_auto_features(symbol, lookback=100):
    """
    Membuat fitur otomatis menggunakan featuretools dari data historis.
    Mengembalikan dataframe dengan fitur tambahan.
    """
    df = ambil_data_dari_db(symbol, hari=lookback+50)
    if df is None:
        return None
    df = tambah_indikator(df)
    df = df.set_index('Date')
    
    # Buat entityset
    es = ft.EntitySet(id="stock")
    es.add_dataframe(
        dataframe_name="prices",
        dataframe=df,
        index="index",
        time_index="Date"
    )
    
    # Generate fitur interaksi
    feature_matrix, feature_defs = ft.dfs(
        entityset=es,
        target_dataframe_name="prices",
        agg_primitives=["mean", "std", "max", "min", "trend"],
        trans_primitives=["add_numeric", "multiply_numeric"],
        max_depth=2,
        verbose=False
    )
    
    return feature_matrixO