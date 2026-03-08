import json
import os

CONFIG_FILE = 'data/paper_config.json'

def load_config():
    """Membaca konfigurasi paper trading."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        return {
            'paper_mode': True,
            'paper_balance': 100_000_000,
            'initial_balance': 100_000_000,
            'open_positions': [],
            'closed_trades': []
        }

def save_config(config):
    os.makedirs('data', exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def toggle_paper_mode():
    config = load_config()
    config['paper_mode'] = not config['paper_mode']
    save_config(config)
    return config['paper_mode']

def reset_paper_balance(new_balance=100_000_000):
    config = load_config()
    config['paper_balance'] = new_balance
    config['initial_balance'] = new_balance
    config['open_positions'] = []
    config['closed_trades'] = []
    save_config(config)