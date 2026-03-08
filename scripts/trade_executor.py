# scripts/trade_executor.py
import logging
import pandas as pd
import sqlite3
import time
from datetime import datetime
from scripts.risk_manager import (
    dynamic_position_size, scaling_in_amounts, should_add_layer,
    scaling_out_targets, scaling_out_sizes, should_take_profit,
    trailing_stop, atr_based_targets, atr_based_stop_loss
)
from scripts.circuit_breaker import is_trading_allowed, increment_trade_count, can_trade, update_loss, get_state_info
from scripts.cooldown_manager import is_cooldown, set_cooldown
from scripts.trade_journal import record_entry, record_exit
from scripts.paper_config import load_config, save_config
from scripts.agent_logger import AgentLogger

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self, account_balance=100_000_000, risk_per_trade=1.5, max_risk_per_trade=3.0):
        self.account_balance = account_balance
        self.risk_per_trade = risk_per_trade
        self.max_risk_per_trade = max_risk_per_trade
        self.positions = {}  # symbol -> posisi

    def check_pre_trade(self, symbol, df, signal):
        allowed, msg = is_trading_allowed()
        if not allowed:
            logger.warning(f"Circuit breaker: {msg}")
            return False, msg
        if not can_trade():
            logger.warning("Batas harian trade tercapai")
            return False, "Batas harian trade (3) tercapai"
        if is_cooldown(symbol):
            logger.warning(f"Cooldown untuk {symbol}")
            return False, f"{symbol} dalam cooldown"
        return True, "OK"

    def close_position_by_signal(self, symbol, df, reason):
        if symbol in self.positions:
            latest = df.iloc[-1]
            exit_price = latest['Close']
            self.execute_exit(symbol, reason, exit_price)
            return True
        return False

    def execute_entry(self, symbol, df, signal, reason, strategy, regime, agent_name='unknown', agent_details=None):
        """
        Execute entry dengan mencatat agen yang terlibat.
        agent_details: list of dict dari multi-agent (opsional)
        """
        if signal != 1:
            logger.info(f"Sinyal {signal} untuk {symbol} diabaikan (hanya long)")
            return

        latest = df.iloc[-1]
        entry_price = latest['Close']
        atr = latest['ATR']

        config = load_config()
        if config['paper_mode']:
            balance = config['paper_balance']
        else:
            balance = self.account_balance

        stop_loss = atr_based_stop_loss(entry_price, atr, atr_multiplier=1.5)
        total_shares = dynamic_position_size(
            balance, entry_price, atr,
            risk_percent=self.risk_per_trade,
            max_risk_percent=self.max_risk_per_trade
        )
        if total_shares == 0:
            logger.warning("Ukuran posisi 0, tidak entry")
            return

        target_prices = atr_based_targets(entry_price, atr, atr_multipliers=[1.5, 2.5, 3.5])
        allocation = [0.3, 0.4, 0.3]
        sizes = scaling_out_sizes(total_shares, allocation)

        cost = sizes[0] * entry_price
        if config['paper_mode']:
            config['paper_balance'] -= cost
            save_config(config)
        else:
            self.account_balance -= cost

        # Catat daftar agen yang terlibat (jika ada)
        agents_involved = []
        if agent_details:
            agents_involved = [d['name'] for d in agent_details]
        else:
            agents_involved = [agent_name]

        self.positions[symbol] = {
            'entry_price': entry_price,
            'total_shares': total_shares,
            'current_shares': sizes[0],
            'layers': [{'size': sizes[0], 'price': entry_price}],
            'current_layer': 1,
            'highest_price': entry_price,
            'atr': atr,
            'stop_loss': stop_loss,
            'reason': reason,
            'strategy': strategy,
            'entry_date': latest['Date'],
            'target_prices': target_prices,
            'target_sizes': sizes,
            'filled_targets': [False, False, False],
            'market_regime': regime,
            'paper_mode': config['paper_mode'],
            'agents': agents_involved  # simpan daftar agen
        }

        increment_trade_count()
        logger.info(f"Entry {symbol}: {sizes[0]} saham di {entry_price}, stop {stop_loss:.2f}, target {target_prices}")
        print(f"✅ ENTRY {symbol}: {sizes[0]} saham di {entry_price} (stop {stop_loss:.2f})")
        record_entry(symbol, str(latest['Date']), entry_price, sizes[0], strategy, reason)

    def check_add_layer(self, symbol, df):
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]
        current_layer = pos['current_layer']
        if current_layer >= 3:
            return
        if should_add_layer(df, current_layer + 1, pos['entry_price']):
            additional = scaling_in_amounts(pos['total_shares'], current_layer + 1)
            if additional > 0:
                latest = df.iloc[-1]
                pos['layers'].append({'size': additional, 'price': latest['Close']})
                pos['current_layer'] += 1
                pos['current_shares'] += additional
                pos['total_shares'] += additional
                logger.info(f"Add layer {pos['current_layer']} for {symbol}: {additional} saham di {latest['Close']}")
                print(f"➕ ADD LAYER {pos['current_layer']} {symbol}: {additional} saham")

    def update_trailing_stop(self, symbol, current_price):
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]
        if current_price > pos['highest_price']:
            pos['highest_price'] = current_price
            new_stop = current_price - (pos['atr'] * 1.5)
            if new_stop > pos['stop_loss']:
                pos['stop_loss'] = new_stop
                logger.info(f"Trailing stop updated for {symbol}: {new_stop:.2f}")

    def check_take_profit(self, symbol, current_price):
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]
        idx = should_take_profit(current_price, pos['entry_price'], pos['target_prices'], pos['filled_targets'])
        if idx != -1:
            size_to_sell = pos['target_sizes'][idx]
            if size_to_sell > 0:
                pos['filled_targets'][idx] = True
                pnl = (current_price - pos['entry_price']) * size_to_sell
                if pos['paper_mode']:
                    config = load_config()
                    config['paper_balance'] += (current_price * size_to_sell)
                    save_config(config)
                else:
                    self.account_balance += pnl
                pos['current_shares'] -= size_to_sell
                pos['total_shares'] -= size_to_sell
                logger.info(f"🎯 Take profit level {idx+1} untuk {symbol}: jual {size_to_sell} saham di {current_price}, PnL {pnl:.2f}")
                print(f"🎯 TAKE PROFIT {symbol} level {idx+1}: jual {size_to_sell} saham di {current_price} (Profit {pnl:.2f})")
            if pos['current_shares'] == 0 or all(pos['filled_targets']):
                self.execute_exit(symbol, 'all_targets_hit', current_price)

    def check_exit(self, symbol, df):
        if symbol not in self.positions:
            return None
        pos = self.positions[symbol]
        latest = df.iloc[-1]
        current_price = latest['Close']
        pos['current_price'] = current_price

        self.update_trailing_stop(symbol, current_price)
        self.check_take_profit(symbol, current_price)

        if current_price <= pos['stop_loss']:
            profit_loss = (current_price - pos['entry_price']) / pos['entry_price'] * 100
            update_loss(-abs(profit_loss))
            set_cooldown(symbol, days=3)
            logger.info(f"Stop loss triggered for {symbol} at {current_price}")
            print(f"🛑 STOP LOSS {symbol}: exit di {current_price} (loss {profit_loss:.2f}%)")
            self.execute_exit(symbol, 'stop_loss', current_price)
            return 'stop_loss'

        entry_date = pos['entry_date']
        if hasattr(entry_date, 'date'):
            days_held = (latest['Date'] - entry_date).days
        else:
            days_held = 0
        if days_held > 10:
            profit_loss = (current_price - pos['entry_price']) / pos['entry_price'] * 100
            print(f"⏰ TIME-BASED EXIT {symbol}: posisi {days_held} hari, ditutup di {current_price} (return {profit_loss:.2f}%)")
            self.execute_exit(symbol, 'time_based', current_price)
            return 'time_based'

        return None

    def execute_exit(self, symbol, reason, exit_price=None):
        if symbol in self.positions:
            pos = self.positions[symbol]
            total_cost = sum(layer['price'] * layer['size'] for layer in pos['layers'])
            avg_entry = total_cost / pos['total_shares']
            if exit_price is None:
                exit_price = pos.get('current_price', avg_entry)
            pnl = (exit_price - avg_entry) * pos['total_shares']
            pnl_pct = (exit_price / avg_entry - 1) * 100
            if pos['paper_mode'] and reason != 'all_targets_hit':
                config = load_config()
                config['paper_balance'] += exit_price * pos['current_shares']
                save_config(config)
            record_exit(symbol, str(pd.Timestamp.now().date()), exit_price, pnl, pnl_pct)

            # ========== UPDATE ACTUAL RETURN UNTUK AGEN YANG TERLIBAT ==========
            try:
                entry_date_str = pos['entry_date'].strftime('%Y-%m-%d') if hasattr(pos['entry_date'], 'strftime') else str(pos['entry_date'])
                for agent_name in pos.get('agents', []):
                    AgentLogger.update_actual_return(symbol, entry_date_str, pnl_pct)
                logger.info(f"Actual return diperbarui untuk {len(pos.get('agents', []))} agen pada {symbol}")
            except Exception as e:
                logger.error(f"Gagal update actual return: {e}")

            del self.positions[symbol]
            logger.info(f"Exit {symbol}, reason: {reason}, PnL: {pnl:.2f}")