import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

_DEFAULT_LOG_LEVEL = os.environ.get("MINER_LOG_LEVEL", "INFO").upper()


def setup_logging(log_directory: str, level: str | int = _DEFAULT_LOG_LEVEL) -> None:
    os.makedirs(log_directory, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(
        fmt='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s","logger":"%(name)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    ))

    # Rotating file handler
    fh = RotatingFileHandler(
        filename=os.path.join(log_directory, "orchestrator.log"),
        maxBytes=50 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(
        fmt='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s","logger":"%(name)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    ))

    # Avoid duplicate handlers if reconfigured
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    root_logger.addHandler(ch)
    root_logger.addHandler(fh)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name)
