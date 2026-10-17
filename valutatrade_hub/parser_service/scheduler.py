"""Планировщик: периодическое обновление курсов по таймеру.

Запуск отдельным процессом:
    uv run python -m valutatrade_hub.parser_service.scheduler
Интервал берётся из SettingsLoader (rates_ttl_seconds), но не меньше 60 сек.
"""
import logging
import time

from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import configure_logging
from valutatrade_hub.parser_service.updater import RatesUpdater

logger = logging.getLogger("valutatrade.parser.scheduler")


def run_scheduler(interval_seconds: int | None = None) -> None:
    settings = SettingsLoader()
    interval = interval_seconds or max(
        int(settings.get("rates_ttl_seconds", 60)), 60
    )
    updater = RatesUpdater()
    logger.info("Scheduler started, interval=%ds", interval)
    try:
        while True:
            try:
                summary = updater.run_update()
                logger.info(
                    "Scheduled update done: %d rates, %d errors",
                    summary["updated"], len(summary["errors"]),
                )
            except Exception:  # планировщик не должен умирать от разового сбоя
                logger.exception("Scheduled update failed")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    settings = SettingsLoader()
    configure_logging(
        settings.get("log_level", "INFO"),
        settings.get("log_dir", "logs"),
    )
    run_scheduler()
