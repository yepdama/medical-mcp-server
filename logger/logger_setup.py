import logging
import os
from config import LOG_LEVEL, LOG_FILE


def get_logger(name: str) -> logging.Logger:
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    # Ensure logs directory exists
    log_file_path = os.path.abspath(LOG_FILE)
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logging once
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        logging.getLogger().addHandler(file_handler)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger


