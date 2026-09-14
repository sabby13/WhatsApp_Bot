"""Local, human-readable logging.

Every important action is logged with a fixed action tag so the flow is easy to
scan and grep: RECEIVED, IGNORED, GENERATED, SENT, ERROR, STARTUP, SHUTDOWN, RAW.
Logs go to stdout and to logs/bot.log. Nothing leaves the machine.
"""
import logging
import sys
from pathlib import Path

_LOG_DIR = Path("logs")


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("whatsapp_bot")
    if logger.handlers:  # already configured
        return logger

    _LOG_DIR.mkdir(exist_ok=True)
    logger.setLevel(level.upper())
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    file_handler = logging.FileHandler(_LOG_DIR / "bot.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
