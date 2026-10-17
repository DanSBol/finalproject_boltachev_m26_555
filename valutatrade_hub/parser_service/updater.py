"""RatesUpdater — точка входа Parser Service: опрос клиентов и сохранение."""
import logging
import time
from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage

logger = logging.getLogger("valutatrade.parser")


class RatesUpdater:
    def __init__(self, clients=None, storage=None, config: ParserConfig | None = None):
        self.config = config or ParserConfig()
        self.storage = storage or RatesStorage(self.config)
        self.clients = clients or [
            CoinGeckoClient(self.config),
            ExchangeRateApiClient(self.config),
        ]

    def run_update(self, source: str | None = None) -> dict:
        """Опрашивает клиентов, собирает курс, пишет кэш и журнал.

        Отказоустойчивость: сбой одного клиента логируется, остальные
        продолжают работу. Возвращает сводку обновления.
        """
        logger.info("Starting rates update...")
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        now_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        pairs: dict[str, dict] = {}
        records: list[dict] = []
        errors: list[str] = []

        for client in self.clients:
            if source and client.source_name.lower() != source.lower():
                continue
            try:
                started = time.perf_counter()
                rates = client.fetch_rates()
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "Fetching from %s... OK (%d rates)",
                    client.source_name, len(rates),
                )
                for pair, rate in rates.items():
                    f_code, t_code = pair.split("_")
                    pairs[pair] = {
                        "rate": rate,
                        "updated_at": now_iso,
                        "source": client.source_name,
                    }
                    records.append({
                        "id": f"{pair}_{now_id}",
                        "from_currency": f_code,
                        "to_currency": t_code,
                        "rate": rate,
                        "timestamp": now_id,
                        "source": client.source_name,
                        "meta": {
                            "request_ms": elapsed_ms,
                            "status_code": 200,
                        },
                    })
            except ApiRequestError as exc:
                logger.error("Failed to fetch from %s: %s", client.source_name, exc)
                errors.append(f"{client.source_name}: {exc}")

        if pairs:
            logger.info(
                "Writing %d rates to %s...",
                len(pairs), self.config.RATES_FILE_PATH,
            )
            self.storage.save_cache(pairs)
            self.storage.append_history(records)

        logger.info(
            "Update finished: %d rates, %d errors",
            len(pairs), len(errors),
        )
        return {
            "updated": len(pairs),
            "errors": errors,
            "last_refresh": now_iso,
        }
