# scripts/walk_forward.py
import itertools
import numpy as np
import pandas as pd
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
import warnings
warnings.filterwarnings('ignore')

class ParamBacktest:
    def __init__(self, initial_capital=100_000_000, fee_buy=0.0015, fee_sell=0.0025, slippage=0.002):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.fee_buy = fee_buy
        self.fee_sell = fee_sell
        self.slippage = slippage
        self.trades = []

    def run(self, df, params):
        self.capital = self.initial_capital
        self.trades = []
        in_position = False
        entry_price = 0
        entry_date = None
        position_size = 0

        start_idx = 50
        if len(df) <= start_idx:
            return self._get_metrics()

        for i in range(start_idx, len(df)):
            df_slice = df.iloc[:i+1].copy()
            latest = df_slice.iloc[-1]
            current_price = latest['Close']
            current_date = latest['Date']

            sig = self._get_signal(df_slice, params)

            if not in_position and sig == 1:
                entry_price = current_price * (1 + self.slippage)
                risk_amount = self.capital * 0.02
                stop_loss = entry_price * 0.95
                risk_per_share = entry_price - stop_loss
                if risk_per_share > 0:
                    position_size = risk_amount / risk_per_share
                    position_size = int(position_size / 100) * 100
                    if position_size >= 100:
                        cost = position_size * entry_price * (1 + self.fee_buy)
                        if cost <= self.capital:
                            self.capital -= cost
                            in_position = True
                            entry_date = current_date

            elif in_position and sig == -1:
                exit_price = current_price * (1 - self.slippage)
                proceeds = position_size * exit_price * (1 - self.fee_sell)
                pnl = proceeds - (position_size * entry_price * (1 + self.fee_buy))
                self.capital += proceeds
                self.trades.append({
                    'entry_date': entry_date,
                    'exit_date': current_date,
                    'pnl': pnl,
                    'pnl_pct': (exit_price / entry_price - 1) * 100
                })
                in_position = False
                position_size = 0
                entry_date = None

        if in_position:
            exit_price = df.iloc[-1]['Close'] * (1 - self.slippage)
            proceeds = position_size * exit_price * (1 - self.fee_sell)
            pnl = proceeds - (position_size * entry_price * (1 + self.fee_buy))
            self.trades.append({
                'entry_date': entry_date,
                'exit_date': df.iloc[-1]['Date'],
                'pnl': pnl,
                'pnl_pct': (exit_price / entry_price - 1) * 100
            })

        return self._get_metrics()

    def _get_signal(self, df_slice, params):
        latest = df_slice.iloc[-1]
        rsi_oversold = params.get('rsi_oversold', 30)
        rsi_overbought = params.get('rsi_overbought', 70)
        adx_threshold = params.get('adx_threshold', 25)

        adx = latest.get('ADX', 0)
        if pd.notna(adx) and adx > adx_threshold:
            regime = 'trending'
        else:
            regime = 'sideways'

        if regime == 'trending':
            if latest['RSI'] < rsi_oversold and latest['Close'] > latest['EMA20']:
                return 1
            elif latest['RSI'] > rsi_overbought and latest['Close'] < latest['EMA20']:
                return -1
        return 0

    def _get_metrics(self):
        if self.trades:
            total_pnl = sum(t['pnl'] for t in self.trades)
            win_trades = [t for t in self.trades if t['pnl'] > 0]
            loss_trades = [t for t in self.trades if t['pnl'] <= 0]
            win_rate = len(win_trades) / len(self.trades) * 100
            avg_win = np.mean([t['pnl'] for t in win_trades]) if win_trades else 0
            avg_loss = np.mean([t['pnl'] for t in loss_trades]) if loss_trades else 0
            profit_factor = abs(sum(t['pnl'] for t in win_trades) / sum(t['pnl'] for t in loss_trades)) if loss_trades and sum(t['pnl'] for t in loss_trades) != 0 else np.inf
        else:
            total_pnl = 0
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0

        return {
            'total_return': (self.capital / self.initial_capital - 1) * 100,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'num_trades': len(self.trades)
        }

def walk_forward(symbol, param_grid, train_years=2, test_years=1, metric='profit_factor'):
    """
    Melakukan walk-forward analysis pada saham tertentu.
    param_grid: list of dict, setiap dict berisi parameter.
    metric: metrik yang digunakan untuk memilih parameter terbaik (profit_factor, sharpe, total_return, win_rate)
    """
    df = ambil_data_dari_db(symbol, hari=1000)
    if df is None or len(df) < 200:
        raise ValueError("Data tidak cukup untuk walk-forward (minimal 200 hari)")

    df = tambah_indikator(df)

    train_days = int(train_years * 252)
    test_days = int(test_years * 252)

    windows = []
    start = 0
    while start + train_days + test_days <= len(df):
        train_end = start + train_days
        test_end = train_end + test_days
        train_df = df.iloc[start:train_end]
        test_df = df.iloc[train_end:test_end]
        windows.append({
            'train': train_df,
            'test': test_df,
            'train_start': train_df.iloc[0]['Date'],
            'train_end': train_df.iloc[-1]['Date'],
            'test_start': test_df.iloc[0]['Date'],
            'test_end': test_df.iloc[-1]['Date']
        })
        start += test_days

    if not windows:
        raise ValueError("Data tidak cukup untuk membuat jendela walk-forward")

    results = []
    for w in windows:
        best_params = None
        best_metric_val = -np.inf
        train_metrics_best = None

        for params in param_grid:
            bt = ParamBacktest()
            train_metrics = bt.run(w['train'], params)
            metric_val = train_metrics.get(metric, -np.inf)
            if metric_val > best_metric_val:
                best_metric_val = metric_val
                best_params = params
                train_metrics_best = train_metrics

        bt_test = ParamBacktest()
        test_metrics = bt_test.run(w['test'], best_params)

        results.append({
            'train_start': w['train_start'],
            'train_end': w['train_end'],
            'test_start': w['test_start'],
            'test_end': w['test_end'],
            'best_params': best_params,
            'train_metrics': train_metrics_best,
            'test_metrics': test_metrics
        })

    return results

def optimize_parameters(symbol, param_grid, method='grid', n_random=50, metric='profit_factor', cv_folds=3, df=None):
    """
    Optimasi parameter dengan grid search atau random search menggunakan walk-forward.
    method: 'grid' atau 'random'
    n_random: jumlah sample untuk random search
    cv_folds: jumlah jendela walk-forward
    df: jika None, ambil dari database berdasarkan symbol; jika diberikan, gunakan df tersebut.
    """
    if df is None:
        df = ambil_data_dari_db(symbol, hari=1000)
        if df is None or len(df) < 500:
            raise ValueError(f"Data tidak cukup untuk {symbol} (minimal 500 hari)")
        df = tambah_indikator(df)
    else:
        # Pastikan df sudah memiliki indikator
        if any(col not in df.columns for col in ['RSI', 'MACD', 'ADX']):
            df = tambah_indikator(df)

    total_len = len(df)
    test_size = int(total_len // (cv_folds + 1))
    train_size = test_size * cv_folds  # sisa untuk train

    if train_size + test_size * cv_folds > total_len:
        test_size = int(total_len // (cv_folds + 1))
        train_size = test_size * cv_folds

    results = []
    for fold in range(cv_folds):
        train_end = train_size + fold * test_size
        test_start = train_end
        test_end = test_start + test_size
        train_df = df.iloc[:train_end]
        test_df = df.iloc[test_start:test_end]

        # Pilih sampel parameter
        if method == 'grid':
            param_list = param_grid
        else:
            # random search: sample n_random dari grid
            if isinstance(param_grid, list):
                param_list = param_grid
            else:
                # jika param_grid adalah dict dengan list nilai, buat kombinasi acak
                keys = list(param_grid.keys())
                values = list(param_grid.values())
                import random
                param_list = []
                for _ in range(min(n_random, len(keys))):
                    param = {}
                    for i, key in enumerate(keys):
                        param[key] = random.choice(values[i])
                    param_list.append(param)

        best_params = None
        best_metric_val = -np.inf
        for params in param_list:
            bt = ParamBacktest()
            train_metrics = bt.run(train_df, params)
            metric_val = train_metrics.get(metric, -np.inf)
            if metric_val > best_metric_val:
                best_metric_val = metric_val
                best_params = params

        # Uji di test
        bt_test = ParamBacktest()
        test_metrics = bt_test.run(test_df, best_params)

        results.append({
            'fold': fold,
            'best_params': best_params,
            'train_metric': best_metric_val,
            'test_metrics': test_metrics
        })

    # Hitung rata-rata test metrics
    avg_test_return = np.mean([r['test_metrics']['total_return'] for r in results])
    avg_test_profit_factor = np.mean([r['test_metrics']['profit_factor'] for r in results])
    avg_test_win_rate = np.mean([r['test_metrics']['win_rate'] for r in results])

    # Pilih parameter terbaik berdasarkan rata-rata test profit factor
    best_params_overall = max(results, key=lambda x: x['test_metrics']['profit_factor'])['best_params']

    return {
        'symbol': symbol,
        'method': method,
        'cv_folds': cv_folds,
        'best_params': best_params_overall,
        'avg_test_return': avg_test_return,
        'avg_test_profit_factor': avg_test_profit_factor,
        'avg_test_win_rate': avg_test_win_rate,
        'fold_results': results
    }

def robustness_test(symbol, base_params, param_variations):
    df = ambil_data_dari_db(symbol, hari=500)
    if df is None or len(df) < 200:
        raise ValueError("Data tidak cukup untuk robustness test")
    df = tambah_indikator(df)

    results = []
    keys = list(param_variations.keys())
    values = list(param_variations.values())
    for combo in itertools.product(*values):
        params = base_params.copy()
        for i, key in enumerate(keys):
            params[key] = base_params[key] + combo[i]
        bt = ParamBacktest()
        metrics = bt.run(df, params)
        results.append({
            'params': params.copy(),
            'metrics': metrics
        })
    return results