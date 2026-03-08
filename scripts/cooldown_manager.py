import json
import os
from datetime import date, timedelta, datetime

COOLDOWN_FILE = 'data/cooldown_saham.json'

def load_cooldown():
    if os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cooldown(cooldown):
    os.makedirs('data', exist_ok=True)
    with open(COOLDOWN_FILE, 'w') as f:
        json.dump(cooldown, f, indent=2)

def set_cooldown(symbol, days=3):
    cooldown = load_cooldown()
    until = date.today() + timedelta(days=days)
    cooldown[symbol] = str(until)
    save_cooldown(cooldown)

def is_cooldown(symbol):
    cooldown = load_cooldown()
    if symbol in cooldown:
        until = datetime.fromisoformat(cooldown[symbol]).date()
        if date.today() <= until:
            return True
        else:
            del cooldown[symbol]
            save_cooldown(cooldown)
    return False