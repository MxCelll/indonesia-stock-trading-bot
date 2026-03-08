import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
from scripts.strategy_selector import get_signal

class BacktestEngine:
    def __init__(self, initial_capital=100_000_000, fee_buy=0.0015, fee_sell=0.0025, slippage=0.002):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.fee_buy = fee_buy
        self.fee_sell = fee_sell
        self.slippage = slippage
        self.trades = []
        self.equity_curve = []

    def run(self, df, symbol):
        self.capital = self.initial_capital
        self.trades = []
        self.equity_curve = []
        in_position = False
        entry_price = 0
        entry_date = None
        position_size = 0

        for i in range(1, len(df)):
            df_slice = df.iloc[:i+1].copy()
            sig, reason, strategy = get_signal(symbol, df_slice)
            current_price = df_slice.iloc[-1]['Close']
            current_date = df_slice.iloc[-1]['Date']

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
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'size': position_size,
                    'pnl': pnl,
                    'pnl_pct': (exit_price / entry_price - 1) * 100
                })
                in_position = False
                position_size = 0
                entry_date = None

            total_value = self.capital
            if in_position:
                total_value += position_size * current_price
            self.equity_curve.append({
                'Date': current_date,
                'Equity': total_value
            })

        if in_position:
            exit_price = df.iloc[-1]['Close'] * (1 - self.slippage)
            proceeds = position_size * exit_price * (1 - self.fee_sell)
            pnl = proceeds - (position_size * entry_price * (1 + self.fee_buy))
            self.capital += proceeds
            self.trades.append({
                'entry_date': entry_date,
                'exit_date': df.iloc[-1]['Date'],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'size': position_size,
                'pnl': pnl,
                'pnl_pct': (exit_price / entry_price - 1) * 100
            })

        equity_df = pd.DataFrame(self.equity_curve)
        return equity_df, self.trades

    def calculate_metrics(self, equity_df, trades):
        if equity_df.empty:
            return {}
        equity_df['Return'] = equity_df['Equity'].pct_change()
        total_return = (equity_df['Equity'].iloc[-1] / self.initial_capital - 1) * 100
        if trades:
            win_trades = [t for t in trades if t['pnl'] > 0]
            loss_trades = [t for t in trades if t['pnl'] <= 0]
            win_rate = len(win_trades) / len(trades) * 100
            avg_win = np.mean([t['pnl'] for t in win_trades]) if win_trades else 0
            avg_loss = np.mean([t['pnl'] for t in loss_trades]) if loss_trades else 0
            profit_factor = abs(sum(t['pnl'] for t in win_trades) / sum(t['pnl'] for t in loss_trades)) if loss_trades and sum(t['pnl'] for t in loss_trades) != 0 else np.inf

            # Hitung rata-rata holding period (hari) dengan konversi tanggal otomatis
            days_list = []
            for t in trades:
                if 'entry_date' in t and 'exit_date' in t:
                    try:
                        if isinstance(t['entry_date'], str):
                            entry = pd.to_datetime(t['entry_date'])
                        else:
                            entry = t['entry_date']
                        if isinstance(t['exit_date'], str):
                            exit = pd.to_datetime(t['exit_date'])
                        else:
                            exit = t['exit_date']
                        days = (exit - entry).days
                        days_list.append(days)
                    except:
                        pass
            avg_holding = np.mean(days_list) if days_list else 0
        else:
            win_rate = avg_win = avg_loss = profit_factor = avg_holding = 0

        equity_df['Peak'] = equity_df['Equity'].cummax()
        equity_df['Drawdown'] = (equity_df['Equity'] - equity_df['Peak']) / equity_df['Peak'] * 100
        max_dd = equity_df['Drawdown'].min()
        returns = equity_df['Return'].dropna()
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0
        return {
            'Total Return (%)': total_return,
            'Win Rate (%)': win_rate,
            'Avg Win': avg_win,
            'Avg Loss': avg_loss,
            'Profit Factor': profit_factor,
            'Max Drawdown (%)': max_dd,
            'Sharpe Ratio': sharpe,
            'Number of Trades': len(trades),
            'Avg Holding (days)': avg_holding
        }

    def get_equity_chart(self, equity_df, symbol):
        if equity_df.empty:
            return None
        if 'Drawdown' not in equity_df.columns:
            equity_df['Peak'] = equity_df['Equity'].cummax()
            equity_df['Drawdown'] = (equity_df['Equity'] - equity_df['Peak']) / equity_df['Peak'] * 100
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
        fig.suptitle(f'Backtest {symbol}', fontsize=14)
        ax1.plot(pd.to_datetime(equity_df['Date']), equity_df['Equity'], color='blue', linewidth=1.5)
        ax1.set_ylabel('Portfolio Value (Rp)')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=self.initial_capital, color='gray', linestyle='--', alpha=0.7, label='Initial Capital')
        ax1.legend()
        ax2.fill_between(pd.to_datetime(equity_df['Date']), 0, equity_df['Drawdown'], color='red', alpha=0.5)
        ax2.set_ylabel('Drawdown (%)')
        ax2.set_xlabel('Date')
        ax2.grid(True, alpha=0.3)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close(fig)
        return buf