# scripts/training_queue.py
import threading
import queue
import logging
import asyncio
from telegram.ext import ContextTypes
from scripts.notifier import bot_loop
from scripts.agent_cache import get_agent_cache

logger = logging.getLogger(__name__)

class TrainingQueue:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        self.queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        self.max_concurrent = 2
        self.current_tasks = 0
        self.task_lock = threading.Lock()
        self.pending_symbols = set()
        self.in_progress = set()
        logger.info("TrainingQueue initialized with max_concurrent=2")

    def _worker(self):
        while True:
            task = self.queue.get()
            symbol = task['symbol']
            model_type = task['model_type']
            key = f"{symbol}_{model_type}"
            with self.task_lock:
                self.pending_symbols.discard(key)
                if self.current_tasks >= self.max_concurrent:
                    self.queue.put(task)
                    self.queue.task_done()
                    continue
                self.current_tasks += 1
                self.in_progress.add(key)
            try:
                self._run_task(task)
            except Exception as e:
                logger.exception(f"Error executing task: {e}")
            finally:
                with self.task_lock:
                    self.current_tasks -= 1
                    self.in_progress.discard(key)
                self.queue.task_done()

    def _run_task(self, task):
        symbol = task['symbol']
        model_type = task['model_type']
        chat_id = task['chat_id']
        context = task['context']

        if model_type == 'ensemble':
            from scripts.ensemble_train import train_ensemble
            try:
                train_ensemble(symbol, tune=False)
                message = f"✅ Model ensemble untuk {symbol} telah selesai dilatih."
                # Invalidasi cache
                cache = get_agent_cache()
                cache.invalidate(symbol)
            except Exception as e:
                logger.exception(f"Ensemble training error: {e}")
                message = f"❌ Gagal melatih model ensemble untuk {symbol}. Periksa log."
        elif model_type == 'lstm':
            from scripts.lstm_predictor import train_lstm
            try:
                train_lstm(symbol, epochs=30)
                message = f"✅ Model LSTM untuk {symbol} telah selesai dilatih."
                cache = get_agent_cache()
                cache.invalidate(symbol)
            except Exception as e:
                logger.exception(f"LSTM training error: {e}")
                message = f"❌ Gagal melatih model LSTM untuk {symbol}. Periksa log."
        else:
            message = f"❌ Tipe model {model_type} tidak dikenal."

        if bot_loop is not None:
            coro = context.bot.send_message(chat_id=chat_id, text=message)
            asyncio.run_coroutine_threadsafe(coro, bot_loop)
        else:
            logger.error("bot_loop not available, cannot send notification")

    def add_task(self, symbol, model_type, chat_id, context):
        key = f"{symbol}_{model_type}"
        with self.task_lock:
            if key in self.pending_symbols or key in self.in_progress:
                logger.info(f"Task {key} already pending or in progress, skipped.")
                return False
            self.pending_symbols.add(key)
        self.queue.put({
            'symbol': symbol,
            'model_type': model_type,
            'chat_id': chat_id,
            'context': context
        })
        logger.info(f"Task added to queue: {symbol} {model_type}")
        return True

    def get_queue_size(self):
        return self.queue.qsize()

    def get_current_tasks(self):
        with self.task_lock:
            return self.current_tasks

# Singleton instance
_training_queue = None

def get_training_queue():
    global _training_queue
    if _training_queue is None:
        _training_queue = TrainingQueue()
    return _training_queue