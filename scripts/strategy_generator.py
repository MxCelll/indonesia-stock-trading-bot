# scripts/strategy_generator.py
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import logging

from scripts.ai_validator_v2 import client, MODEL_NAME
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
from scripts.walk_forward import ParamBacktest

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StrategyGenerator:
    """
    Menghasilkan dan menguji strategi trading menggunakan LLM.
    """
    
    def __init__(self, symbol, target_days=5):
        self.symbol = symbol
        self.target_days = target_days
        self.conn = sqlite3.connect('data/saham.db')
    
    def fetch_data(self, days=300):
        """Ambil data historis untuk saham."""
        df = ambil_data_dari_db(self.symbol, hari=days)
        if df is None or len(df) < 100:
            raise ValueError(f"Data tidak cukup untuk {self.symbol}")
        df = tambah_indikator(df)
        # Pastikan kolom Date ada sebagai index
        if 'Date' in df.columns:
            df.set_index('Date', inplace=True)
        return df
    
    def generate_strategy_prompt(self, df):
        """Buat prompt yang lebih baik untuk LLM."""
        latest = df.iloc[-1]
        mean_volume = df['Volume'].mean()
        mean_atr = df['ATR'].mean()
        
        # Daftar kolom yang tersedia
        available_columns = [
            'RSI', 'MACD', 'MACD_signal', 'MACD_diff', 
            'EMA20', 'EMA50', 'EMA200',
            'ADX', 'DI_plus', 'DI_minus',
            'Volume', 'Volume_MA20', 'ATR', 'Close', 'Open', 'High', 'Low'
        ]
        
        prompt = f"""
        Anda adalah ahli strategi trading untuk saham Indonesia. Buat SATU strategi trading sederhana berdasarkan indikator teknikal untuk saham {self.symbol}.

        Data statistik terbaru:
        - Harga Close: {latest['Close']:.2f}
        - RSI: {latest['RSI']:.2f}
        - ADX: {latest['ADX']:.2f}
        - Volume rata-rata: {mean_volume:.0f}
        - ATR rata-rata: {mean_atr:.2f}

        Kolom yang tersedia: {', '.join(available_columns)}.
        Gunakan nama kolom persis seperti di atas.

        Strategi harus memiliki kondisi entry dan exit yang sederhana, realistis, dan diharapkan dapat menghasilkan minimal 5 sinyal dalam 300 hari data historis.
        Gunakan threshold yang tidak terlalu ekstrem, misalnya RSI antara 30-40 untuk oversold, dan antara 60-70 untuk overbought. Contoh kondisi entry yang baik: RSI < 35 AND Volume > Volume_MA20 AND Close > EMA20.

        Gunakan operator perbandingan standar: <, >, <=, >=, ==. Jangan gunakan operator seperti "crosses_above" atau "crosses_below".

        Berikan strategi dalam format JSON dengan struktur berikut. Pastikan JSON valid:
        {{
            "name": "Nama Strategi",
            "description": "Penjelasan singkat",
            "entry_conditions": [
                {{"indicator": "RSI", "operator": "<", "value": 35}},
                {{"indicator": "Volume", "operator": ">", "value": "Volume_MA20"}},
                {{"indicator": "Close", "operator": ">", "value": "EMA20"}}
            ],
            "exit_conditions": [
                {{"indicator": "RSI", "operator": ">", "value": 65}},
                {{"indicator": "Close", "operator": "<", "value": "EMA20"}}
            ],
            "stop_loss_pct": 5.0,
            "take_profit_pct": 10.0
        }}

        Gunakan nilai numerik untuk threshold. Jika value adalah indikator lain, tulis sebagai string, misal "EMA20". Maksimal 3 kondisi per entry/exit.
        """
        return prompt
    
    def parse_strategy(self, text):
        """Parse respons LLM menjadi dictionary strategi."""
        try:
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
            strategy = json.loads(text)
            return strategy
        except Exception as e:
            logging.error(f"Gagal parse strategi: {e}")
            return None
    
    def conditions_to_function(self, conditions, df):
        """Konversi daftar kondisi menjadi boolean series."""
        if not conditions:
            return pd.Series(True, index=df.index)
        
        result = pd.Series(True, index=df.index)
        for cond in conditions:
            ind = cond.get('indicator')
            op = cond.get('operator')
            val = cond.get('value')
            
            if ind is None or op is None or val is None:
                logging.warning(f"Kondisi tidak lengkap: {cond}")
                continue
            
            # Pastikan indikator ada di kolom
            if ind not in df.columns:
                logging.warning(f"Indikator {ind} tidak dikenal, lewati kondisi")
                continue
            
            data = df[ind]
            
            # Jika value adalah string dan ada di kolom, bandingkan antar kolom
            if isinstance(val, str) and val in df.columns:
                if op == '>':
                    result &= (data > df[val])
                elif op == '<':
                    result &= (data < df[val])
                elif op == '>=':
                    result &= (data >= df[val])
                elif op == '<=':
                    result &= (data <= df[val])
                elif op == '==':
                    result &= (data == df[val])
                else:
                    logging.warning(f"Operator {op} tidak dikenal")
                continue
            
            # Jika value adalah angka, konversi ke float
            try:
                num_val = float(val)
            except:
                logging.warning(f"Value {val} tidak dapat dikonversi ke float dan bukan kolom, lewati")
                continue
            
            if op == '>':
                result &= (data > num_val)
            elif op == '<':
                result &= (data < num_val)
            elif op == '>=':
                result &= (data >= num_val)
            elif op == '<=':
                result &= (data <= num_val)
            elif op == '==':
                result &= (data == num_val)
            else:
                logging.warning(f"Operator {op} tidak dikenal")
        
        return result
    
    def backtest_strategy(self, df, strategy):
        """Jalankan backtest sederhana berdasarkan strategi yang diberikan."""
        entry_signal = self.conditions_to_function(strategy.get('entry_conditions', []), df)
        exit_signal = self.conditions_to_function(strategy.get('exit_conditions', []), df)
        
        logging.info(f"Jumlah entry signal: {entry_signal.sum()}")
        logging.info(f"Jumlah exit signal: {exit_signal.sum()}")
        
        in_position = False
        trades = []
        capital = 100_000_000
        initial_capital = capital
        max_holding_days = 10  # keluar otomatis setelah 10 hari
        
        for i in range(1, len(df)):
            if not in_position and entry_signal.iloc[i]:
                entry_price = df['Close'].iloc[i]
                in_position = True
                entry_date = df.index[i]
            elif in_position and exit_signal.iloc[i]:
                exit_price = df['Close'].iloc[i]
                pnl = (exit_price - entry_price) * 100
                pnl_pct = (exit_price / entry_price - 1) * 100
                trades.append({
                    'entry_date': entry_date,
                    'exit_date': df.index[i],
                    'pnl': pnl,
                    'pnl_pct': pnl_pct
                })
                capital += pnl
                in_position = False
            elif in_position:
                # Cek apakah sudah terlalu lama tanpa exit
                days_held = (df.index[i] - entry_date).days
                if days_held >= max_holding_days:
                    exit_price = df['Close'].iloc[i]
                    pnl = (exit_price - entry_price) * 100
                    pnl_pct = (exit_price / entry_price - 1) * 100
                    trades.append({
                        'entry_date': entry_date,
                        'exit_date': df.index[i],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct
                    })
                    capital += pnl
                    in_position = False
        
        if not trades:
            return {
                'total_return': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'sharpe': 0,
                'num_trades': 0
            }
        
        total_return = (capital / initial_capital - 1) * 100
        win_trades = [t for t in trades if t['pnl'] > 0]
        loss_trades = [t for t in trades if t['pnl'] <= 0]
        win_rate = len(win_trades) / len(trades) * 100
        profit_factor = abs(sum(t['pnl'] for t in win_trades) / sum(t['pnl'] for t in loss_trades)) if loss_trades else np.inf
        
        # Drawdown sederhana
        equity = initial_capital
        equity_curve = []
        for t in trades:
            equity += t['pnl']
            equity_curve.append(equity)
        if len(equity_curve) > 0:
            peak = np.maximum.accumulate(equity_curve)
            drawdown = (equity_curve - peak) / peak * 100
            max_dd = drawdown.min()
        else:
            max_dd = 0
        
        returns = [t['pnl_pct'] for t in trades]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
        
        return {
            'total_return': total_return,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_dd,
            'sharpe': sharpe,
            'num_trades': len(trades)
        }
        
        total_return = (capital / initial_capital - 1) * 100
        win_trades = [t for t in trades if t['pnl'] > 0]
        loss_trades = [t for t in trades if t['pnl'] <= 0]
        win_rate = len(win_trades) / len(trades) * 100
        profit_factor = abs(sum(t['pnl'] for t in win_trades) / sum(t['pnl'] for t in loss_trades)) if loss_trades else np.inf
        
        # Drawdown sederhana
        equity = initial_capital
        equity_curve = []
        for t in trades:
            equity += t['pnl']
            equity_curve.append(equity)
        if len(equity_curve) > 0:
            peak = np.maximum.accumulate(equity_curve)
            drawdown = (equity_curve - peak) / peak * 100
            max_dd = drawdown.min()
        else:
            max_dd = 0
        
        returns = [t['pnl_pct'] for t in trades]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
        
        return {
            'total_return': total_return,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_dd,
            'sharpe': sharpe,
            'num_trades': len(trades)
        }
    
    def save_experiment(self, strategy, metrics):
        """Simpan hasil eksperimen ke database."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO strategy_experiments 
            (symbol, strategy_name, parameters, total_return, win_rate, profit_factor, max_drawdown, sharpe, num_trades)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.symbol,
            strategy.get('name', 'Unknown'),
            json.dumps(strategy),
            metrics['total_return'],
            metrics['win_rate'],
            metrics['profit_factor'],
            metrics['max_drawdown'],
            metrics['sharpe'],
            metrics['num_trades']
        ))
        self.conn.commit()
    
    def run_generation_cycle(self, max_iterations=5):
        """Jalankan siklus generate-backtest berulang."""
        df = self.fetch_data()
        
        for i in range(max_iterations):
            logging.info(f"Iterasi {i+1}/{max_iterations} untuk {self.symbol}")
            prompt = self.generate_strategy_prompt(df)
            
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1000
                )
                text = response.choices[0].message.content
                strategy = self.parse_strategy(text)
                if not strategy:
                    continue
                
                metrics = self.backtest_strategy(df, strategy)
                self.save_experiment(strategy, metrics)
                logging.info(f"Strategi {strategy.get('name', 'Tanpa Nama')} selesai: Return {metrics['total_return']:.2f}%, Win Rate {metrics['win_rate']:.1f}%")
                
            except Exception as e:
                logging.error(f"Error pada iterasi {i}: {e}")
                continue
    
    def close(self):
        self.conn.close()