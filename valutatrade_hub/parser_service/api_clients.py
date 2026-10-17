"""Клиенты внешних API: единый интерфейс fetch_rates() для всех источников."""
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Абстрактный клиент: отдаёт курсы в едином формате FROM_TO."""

    source_name: str = "base"
    source_key: str = "base"

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Возвращает {'FROM_TO': rate, ...}. При сбое — ApiRequestError."""

    def _raise(self, message: str) -> None:
        raise ApiRequestError(f"{self.source_name}: {message}")


class CoinGeckoClient(BaseApiClient):
    """Криптовалюты. ID монет берутся из CRYPTO_ID_MAP (тикер != ID)."""

    source_name = "CoinGecko"
    source_key = "coingecko"

    def fetch_rates(self) -> dict[str, float]:
        ids = ",".join(
            self.config.CRYPTO_ID_MAP[code]
            for code in self.config.CRYPTO_CURRENCIES
            if code in self.config.CRYPTO_ID_MAP
        )
        base = self.config.BASE_CURRENCY
        try:
            response = requests.get(
                self.config.COINGECKO_URL,
                params={"ids": ids, "vs_currencies": base.lower()},
                timeout=self.config.REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as exc:
            self._raise(f"Сетевая ошибка: {exc}")

        if response.status_code == 429:
            self._raise("превышен лимит запросов (429)")
        if response.status_code != 200:
            self._raise(f"HTTP {response.status_code}")

        data = response.json()
        id_to_code = {v: k for k, v in self.config.CRYPTO_ID_MAP.items()}
        result: dict[str, float] = {}
        for coin_id, values in data.items():
            code = id_to_code.get(coin_id)
            rate = values.get(base.lower()) if isinstance(values, dict) else None
            if code and isinstance(rate, (int, float)) and rate > 0:
                result[f"{code}_{base}"] = float(rate)
        return result


class ExchangeRateApiClient(BaseApiClient):
    """Фиатные валюты. Ключ подставляется в URL, база — USD."""

    source_name = "ExchangeRate-API"
    source_key = "exchangerate"

    def fetch_rates(self) -> dict[str, float]:
        if not self.config.EXCHANGERATE_API_KEY:
            self._raise("не задан ключ EXCHANGERATE_API_KEY")

        url = (
            f"{self.config.EXCHANGERATE_API_URL}/"
            f"{self.config.EXCHANGERATE_API_KEY}/latest/{self.config.BASE_CURRENCY}"
        )
        try:
            response = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            self._raise(f"Сетевая ошибка: {exc}")

        if response.status_code == 429:
            self._raise("превышен лимит запросов (429)")
        if response.status_code in (401, 403):
            self._raise("неверный API-ключ")
        if response.status_code != 200:
            self._raise(f"HTTP {response.status_code}")

        data = response.json()
        if data.get("result") != "success":
            self._raise(f"API вернул ошибку: {data.get('error-type', 'unknown')}")

        rates = data.get("conversion_rates") or data.get("rates") or {}

        base = self.config.BASE_CURRENCY
        result: dict[str, float] = {}
        for code in self.config.FIAT_CURRENCIES:
            rate = rates.get(code)
            # rates[code] — сколько code за 1 USD; наша конвенция FROM_TO
            if not isinstance(rate, (int, float)) or rate <= 0:
                continue
            result[f"{base}_{code}"] = round(float(rate), 6)
            if code != base:
                result[f"{code}_{base}"] = round(1.0 / float(rate), 6)
        return result
