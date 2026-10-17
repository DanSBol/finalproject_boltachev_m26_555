"""Настройка логирования: формат, уровень, ротация файлов."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(levelname)s %(asctime)s %(name)s %(message)s"

_configured = False


def configure_logging(level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    """Настраивает корневой логгер проекта. Повторный вызов — безопасен."""
    global _configured
    logger = logging.getLogger("valutatrade")

    if _configured:
        return logger

    Path(log_dir).mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        Path(log_dir) / "actions.log",
        maxBytes=1_000_000,   # 1 МБ на файл
        backupCount=5,        # до 5 старых файлов
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False  # не дублировать в корневой логгер Python

    _configured = True
    return logger
