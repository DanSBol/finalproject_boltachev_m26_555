"""Декоратор @log_action — трассировка доменных операций."""
import functools
import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger("valutatrade.actions")


def log_action(action: str, verbose: bool = False) -> Callable:
    """Логирует вызов функции: ключевые поля + result OK/ERROR.

    Исключения НЕ глотаются — фиксируются в лог и пробрасываются дальше.
    При verbose=True добавляется контекст (например, состояние кошелька).
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Связываем аргументы с именами параметров функции,
            # чтобы одинаково ловить и позиционные, и именованные вызовы
            bound = inspect.signature(func).bind(*args, **kwargs)
            bound.apply_defaults()
            fields = bound.arguments

            parts = [
                f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
                action,
                f"user='{fields.get('user_id') or fields.get('username')}'",
                f"currency='{fields.get('currency_code', '')}'",
                f"amount={fields.get('amount', '')}",
            ]
            if verbose:
                parts.append(f"context={fields}")

            try:
                result = func(*args, **kwargs)
                logger.info(" ".join(parts) + " result=OK")
                return result
            except Exception as exc:
                logger.error(
                    " ".join(parts)
                    + f" result=ERROR error_type={type(exc).__name__}"
                    + f" error_message='{exc}'"
                )
                raise

        return wrapper
    return decorator
