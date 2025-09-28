"""logger.py
Structured logging utilities for the portfolio rebalancer.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def get_logger(
    name: str = "portfolio_rebalancer",
    level: int = logging.INFO,
    log_path: Optional[Path] = None,
) -> logging.Logger:
    """Return a configured logger with console and rotating file handlers.

    Parameters
    - name: Logger name
    - level: Logging level
    - log_path: Optional explicit path for the log file; defaults to rebalancer.log next to this file
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Rotating file handler
    if log_path is None:
        log_path = Path(__file__).with_name("rebalancer.log")
    fh = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger
