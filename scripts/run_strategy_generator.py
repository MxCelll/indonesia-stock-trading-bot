# scripts/run_strategy_generator.py
import logging
import argparse
from scripts.strategy_generator import StrategyGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description='Generate and backtest trading strategies using LLM.')
    parser.add_argument('symbol', help='Kode saham (misal: BBCA.JK)')
    parser.add_argument('--iterations', type=int, default=5, help='Jumlah iterasi')
    args = parser.parse_args()
    
    generator = StrategyGenerator(args.symbol)
    try:
        generator.run_generation_cycle(max_iterations=args.iterations)
    finally:
        generator.close()

if __name__ == "__main__":
    main()