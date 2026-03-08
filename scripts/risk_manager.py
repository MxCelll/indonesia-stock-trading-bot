import numpy as np

def calculate_position_size(account_balance, risk_percent, entry_price, stop_loss_price=None, atr=None, atr_multiplier=1.5):
    risk_amount = account_balance * (risk_percent / 100)
    if stop_loss_price is None and atr is not None:
        stop_loss_price = entry_price - (atr * atr_multiplier)
    if stop_loss_price is None:
        raise ValueError("Stop loss harus ditentukan")
    risk_per_share = abs(entry_price - stop_loss_price)
    if risk_per_share == 0:
        return 0
    position_size = risk_amount / risk_per_share
    position_size = int(position_size / 100) * 100
    return max(position_size, 100)

def dynamic_position_size(account_balance, entry_price, atr, risk_percent=1.5, max_risk_percent=3.0):
    if atr is None or atr == 0:
        return calculate_position_size(account_balance, risk_percent, entry_price, atr=atr)
    base_size = calculate_position_size(account_balance, risk_percent, entry_price, atr=atr)
    atr_pct = (atr / entry_price) * 100
    if atr_pct > 5:
        reduction_factor = 5 / atr_pct
        adjusted_size = int(base_size * reduction_factor)
        return max(adjusted_size, 100)
    else:
        return base_size

def scaling_in_amounts(total_position, layer=1):
    if layer == 1:
        return int(total_position * 0.3)
    elif layer == 2:
        return int(total_position * 0.4)
    elif layer == 3:
        return int(total_position * 0.3)
    else:
        return 0

def should_add_layer(df, layer, entry_price):
    latest = df.iloc[-1]
    if layer == 2:
        return latest['Close'] > latest['EMA20'] and latest['RSI'] > 50
    elif layer == 3:
        return (latest['Volume'] > latest['Volume_MA20'] and latest['RSI'] > 60)
    return False

def scaling_out_targets(entry_price, profit_targets=[0.03, 0.06, 0.10]):
    return [entry_price * (1 + p) for p in profit_targets]

def scaling_out_sizes(total_shares, allocation=[0.3, 0.4, 0.3]):
    return [int(total_shares * a) for a in allocation]

def should_take_profit(current_price, entry_price, target_levels, filled_levels):
    for i, target in enumerate(target_levels):
        if not filled_levels[i] and current_price >= target:
            return i
    return -1

def trailing_stop(current_price, highest_since_entry, atr, trail_atr_multiple=2):
    stop_level = highest_since_entry - (atr * trail_atr_multiple)
    return stop_level

def calculate_stop_loss(entry_price, atr, atr_multiplier=1.5, method='atr'):
    if method == 'atr':
        return entry_price - (atr * atr_multiplier)
    elif method == 'percent':
        percent = atr_multiplier / 100
        return entry_price * (1 - percent)
    else:
        raise ValueError("Method tidak dikenal")

def adjust_stop_loss(current_price, position, market_regime):
    if market_regime == 'trending':
        new_stop = trailing_stop(current_price, position['highest_price'], position['atr'], trail_atr_multiple=2)
    else:
        new_stop = position['stop_loss']
    return max(new_stop, position['stop_loss'])

def atr_based_targets(entry_price, atr, atr_multipliers=[1.5, 2.5, 3.5]):
    return [entry_price + (atr * mult) for mult in atr_multipliers]

def atr_based_stop_loss(entry_price, atr, atr_multiplier=1.5):
    return entry_price - (atr * atr_multiplier)