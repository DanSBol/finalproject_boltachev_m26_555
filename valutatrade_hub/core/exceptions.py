"""Пользовательские исключения valutatrade_hub.

Каждое исключение знает свой пользовательский текст сообщения —
CLI перехватывает их и печатает как есть.
"""


class ValutatradeError(Exception):
    """Базовое исключение проекта — на него можно ловить всё сразу."""


class InsufficientFundsError(ValutatradeError):
    """Недостаточно средств для операции."""

    def __init__(self, available: float, required: float, code: str):
        self.available = available
        self.required = required
        self.code = code
        super().__init__(
            f"Недостаточно средств: доступно {available:.2f} {code}, "
            f"требуется {required:.2f} {code}"
        )


class CurrencyNotFoundError(ValutatradeError):
    """Неизвестный код валюты."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(ValutatradeError):
    """Сбой при обращении к внешнему API курсов."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
