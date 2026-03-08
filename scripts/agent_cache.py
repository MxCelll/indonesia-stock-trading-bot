# scripts/agent_cache.py
import time
import logging

logger = logging.getLogger(__name__)

class AgentCache:
    def __init__(self):
        self._cache = {}
        self._ttl = 3600  # 1 jam

    def get(self, symbol):
        """Mengembalikan data cache jika masih valid, None jika kedaluwarsa atau tidak ada."""
        data = self._cache.get(symbol)
        if data:
            if time.time() - data['timestamp'] < self._ttl:
                logger.debug(f"Cache hit for {symbol}")
                return data['result']
            else:
                logger.debug(f"Cache expired for {symbol}")
                del self._cache[symbol]
        return None

    def set(self, symbol, result):
        """Menyimpan hasil analisis ke cache."""
        self._cache[symbol] = {
            'timestamp': time.time(),
            'result': result
        }
        logger.debug(f"Cache set for {symbol}")

    def invalidate(self, symbol):
        """Menghapus cache untuk simbol tertentu."""
        if symbol in self._cache:
            del self._cache[symbol]
            logger.info(f"Cache invalidated for {symbol}")

    def clear(self):
        """Menghapus semua cache."""
        self._cache.clear()
        logger.info("Cache cleared")

# Singleton instance
_agent_cache = None

def get_agent_cache():
    global _agent_cache
    if _agent_cache is None:
        _agent_cache = AgentCache()
    return _agent_cache