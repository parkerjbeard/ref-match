import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from config.config import Config


def setup_logger(name='refmatch'):
    """Set up application logger with file and console handlers"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(Config.LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name=None):
    """Get logger instance"""
    return logging.getLogger(name or 'refmatch')


# Create default logger
logger = setup_logger()