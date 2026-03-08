# scripts/update_sectors.py
import logging
from scripts.sector_rotation import get_sector_analyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def update_all_sectors():
    analyzer = get_sector_analyzer()
    analyzer.update_all_clusters()
    logging.info("Update sektor selesai.")

if __name__ == "__main__":
    update_all_sectors()