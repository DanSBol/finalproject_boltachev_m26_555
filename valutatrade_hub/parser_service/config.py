"""Конфигурация Parser Service.

Ключ API не хранится в коде: читается из переменной окружения
EXCHANGERATE_API_KEY или из файла .env (не отслеживается git).
"""
import os
from dataclasses import dataclass
from typing import ClassVar

try:  # python-dotenv — опционально, для удобства локальной разработки
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


@dataclass
class ParserConfig:
    # Ключ загружается из переменной окружения
    EXCHANGERATE_API_KEY: str = os.getenv("EXCHANGERATE_API_KEY", "")

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Списки валют
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: ClassVar[dict] = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
    }

    # Пути к файлам
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    # Сетевые параметры
    REQUEST_TIMEOUT: int = 10
