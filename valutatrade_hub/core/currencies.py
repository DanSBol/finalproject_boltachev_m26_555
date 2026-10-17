"""Иерархия валют: ABC Currency, наследники Fiat/Crypto и реестр."""
from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Базовая валюта.

    Инварианты: code — верхний регистр, 2–5 символов, без пробелов;
    name — непустая строка.
    """

    def __init__(self, code: str, name: str):
        if not isinstance(code, str) or not 2 <= len(code) <= 5 or " " in code:
            raise ValueError(f"Некорректный код валюты: '{code}'")
        if code != code.upper():
            raise ValueError(f"Код валюты должен быть в верхнем регистре: '{code}'")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")

        self.code = code
        self.name = name

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление для UI/логов."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.code}>"


class FiatCurrency(Currency):
    """Фиатная валюта: есть страна/зона эмиссии."""

    def __init__(self, code: str, name: str, issuing_country: str):
        super().__init__(code, name)
        if not issuing_country.strip():
            raise ValueError("Страна эмиссии не может быть пустой")
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта: алгоритм и известная капитализация."""

    def __init__(self, code: str, name: str, algorithm: str, market_cap: float):
        super().__init__(code, name)
        if not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым")
        if market_cap < 0:
            raise ValueError("Капитализация не может быть отрицательной")
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        # 1.12e+12 -> 1.12e12, как в примере задания
        mcap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {mcap})"
        )


SUPPORTED_CURRENCIES: dict[str, Currency] = {
    "USD": FiatCurrency("USD", "US Dollar", "United States"),
    "EUR": FiatCurrency("EUR", "Euro", "Eurozone"),
    "GBP": FiatCurrency("GBP", "Pound Sterling", "United Kingdom"),
    "RUB": FiatCurrency("RUB", "Russian Ruble", "Russia"),
    "BTC": CryptoCurrency("BTC", "Bitcoin", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("ETH", "Ethereum", "Ethash", 4.05e11),
}


def get_currency(code: str) -> Currency:
    """Фабрика: возвращает валюту по коду или бросает CurrencyNotFoundError."""
    currency = SUPPORTED_CURRENCIES.get(code)
    if currency is None:
        raise CurrencyNotFoundError(code)
    return currency
