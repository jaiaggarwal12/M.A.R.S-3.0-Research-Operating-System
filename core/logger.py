import sys
from loguru import logger
from core import config
logger.remove()
logger.add(sys.stderr, level=config.LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
    colorize=True)
logger.add(config.LOG_FILE, level="DEBUG", rotation="10 MB", retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}")
__all__ = ["logger"]
