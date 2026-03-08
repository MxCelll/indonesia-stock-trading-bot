# scripts/train_rl.py
import logging
from scripts.rl_agent import RLOrchestrator
from scripts.agent_logger import AgentLogger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def train_rl_orchestrator(days_back=90):
    """
    Melatih RL orchestrator dari data historis.
    """
    logging.info(f"Memulai training RL orchestrator (data {days_back} hari terakhir)...")
    
    # Siapkan data training
    df = RLOrchestrator.prepare_training_data(days_back)
    if df is None or df.empty:
        logging.warning("Tidak cukup data untuk training RL.")
        return False
    
    # Inisialisasi agent
    rl_agent = RLOrchestrator()
    
    # Training
    rl_agent.train_from_history(df)
    
    logging.info(f"Training selesai. Q-table shape: {rl_agent.q_table.shape}")
    logging.info(f"Q-table:\n{rl_agent.q_table}")
    
    return True

if __name__ == "__main__":
    train_rl_orchestrator(days_back=90)