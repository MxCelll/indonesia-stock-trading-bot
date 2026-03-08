import json
import os
from datetime import date, datetime, timedelta

STATE_FILE = 'data/circuit_state.json'

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    else:
        return {
            'daily_loss': 0.0,
            'daily_loss_date': str(date.today()),
            'daily_loss_cap': 5.0,
            'daily_loss_hit_count': 0,
            'monthly_loss': 0.0,
            'monthly_loss_month': str(date.today().month),
            'cooldown_until': None,
            'crash_mode': False,
            'trade_count': 0,
            'trade_date': str(date.today())
        }

def save_state(state):
    os.makedirs('data', exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def update_loss(profit_loss_pct):
    state = load_state()
    today = str(date.today())
    this_month = str(date.today().month)
    if state['daily_loss_date'] != today:
        state['daily_loss'] = 0.0
        state['daily_loss_date'] = today
    if state['monthly_loss_month'] != this_month:
        state['monthly_loss'] = 0.0
        state['monthly_loss_month'] = this_month
        state['daily_loss_hit_count'] = 0
    if profit_loss_pct < 0:
        state['daily_loss'] += abs(profit_loss_pct)
        state['monthly_loss'] += abs(profit_loss_pct)
    save_state(state)

def is_trading_allowed():
    state = load_state()
    if state.get('cooldown_until'):
        cooldown_date = datetime.fromisoformat(state['cooldown_until']).date()
        if date.today() <= cooldown_date:
            return False, f"Cooldown sampai {cooldown_date}"
    if state['daily_loss'] >= state['daily_loss_cap']:
        cooldown_until = date.today() + timedelta(days=1)
        state['cooldown_until'] = str(cooldown_until)
        state['daily_loss_hit_count'] = state.get('daily_loss_hit_count', 0) + 1
        if state['daily_loss_hit_count'] >= 3:
            state['daily_loss_hit_count'] = 0
            cooldown_until = date.today() + timedelta(days=3)
            state['cooldown_until'] = str(cooldown_until)
        save_state(state)
        return False, f"Daily loss cap {state['daily_loss_cap']}% tercapai, trading dihentikan sampai {cooldown_until}"
    if state['monthly_loss'] >= 15.0:
        cooldown_until = date.today() + timedelta(days=7)
        state['cooldown_until'] = str(cooldown_until)
        save_state(state)
        return False, f"Monthly loss limit 15% tercapai, cooldown 7 hari sampai {cooldown_until}"
    if state.get('crash_mode'):
        return False, "Market crash mode aktif"
    return True, "OK"

def set_daily_loss_cap(new_cap):
    state = load_state()
    state['daily_loss_cap'] = float(new_cap)
    save_state(state)

def increment_trade_count():
    state = load_state()
    today = str(date.today())
    if state.get('trade_date') != today:
        state['trade_count'] = 1
        state['trade_date'] = today
    else:
        state['trade_count'] = state.get('trade_count', 0) + 1
    save_state(state)
    return state['trade_count']

def can_trade(max_trades=3):
    state = load_state()
    today = str(date.today())
    if state.get('trade_date') != today:
        return True
    return state.get('trade_count', 0) < max_trades

def set_crash_mode(active=True):
    state = load_state()
    state['crash_mode'] = active
    save_state(state)

def get_state_info():
    state = load_state()
    return {
        'daily_loss': state['daily_loss'],
        'daily_loss_cap': state['daily_loss_cap'],
        'monthly_loss': state['monthly_loss'],
        'trade_count': state['trade_count'],
        'cooldown_until': state.get('cooldown_until'),
        'crash_mode': state['crash_mode']
    }