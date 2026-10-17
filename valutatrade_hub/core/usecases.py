"""Бизнес-логика: register/login, портфель, buy/sell, get-rate.

Все операции хранилища идут через DatabaseManager (синглтон),
конфигурация — через SettingsLoader (синглтон),
ключевые операции логируются декоратором @log_action.

Курсы берутся из локального кэша data/rates.json (формат Parser Service:
{"pairs": {"FROM_TO": {"rate": ..., "updated_at": ..., "source": ...}}});
при устаревании (TTL из SettingsLoader) выполняется обновление через
Parser Service. Поддерживается и плоский формат {"FROM_TO": {...}}.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader


@log_action(action="REGISTER")
def register_user(username: str, password: str) -> Dict[str, Any]:
    """Регистрирует нового пользователя и создаёт портфель со стартовым капиталом."""
    existing = User.find_by_username(username)
    if existing:
        raise ValueError(f"Имя пользователя '{username}' уже занято.")

    if len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов.")

    user_id = User.next_user_id()
    salt = User.generate_salt()
    hashed = User.hash_password(password, salt)
    reg_date = datetime.now(timezone.utc).isoformat()

    new_user = User(
        user_id=user_id,
        username=username,
        hashed_password=hashed,
        salt=salt,
        registration_date=reg_date,
    )

    users = User.load_all_users()
    users.append(new_user)
    User.save_users(users)

    db = DatabaseManager()
    portfolios = db.load("portfolios.json", [])
    portfolios.append({"user_id": user_id, "wallets": {"USD": 10000.0}})
    db.save("portfolios.json", portfolios)

    return {
        "user_id": new_user.user_id,
        "username": new_user.username,
        "registration_date": reg_date,
    }


@log_action(action="LOGIN")
def login_user(username: str, password: str) -> Dict[str, Any]:
    """Выполняет вход пользователя, проверяет логин и пароль."""
    user = User.find_by_username(username)
    if not user:
        raise ValueError("Пользователь не найден.")
    if not user.verify_password(password):
        raise ValueError("Неверный пароль.")
    return {"user_id": user.user_id, "username": user.username}


def get_rate(from_code: str, to_code: str) -> tuple[float, Optional[str], str]:
    """Возвращает (курс, updated_at, ключ пары) с учётом TTL и кросс-курсов.

    Порядок поиска: прямая пара → обратная пара → кросс-курс через USD.
    Если запись есть, но устарела (TTL из SettingsLoader) — обновление
    через Parser Service; сбой обновления оборачивается в ApiRequestError.
    """
    f_code = from_code.strip().upper()
    t_code = to_code.strip().upper()
    get_currency(f_code)   # CurrencyNotFoundError при неизвестном коде
    get_currency(t_code)

    if f_code == t_code:
        return 1.0, None, f"{f_code}_{t_code}"

    db = DatabaseManager()
    ttl = int(SettingsLoader().get("rates_ttl_seconds", 60))
    now = datetime.now(timezone.utc)

    result = _compute_rate(_load_cached_pairs(db), f_code, t_code)

    if result is None or not _is_fresh(result[1], now, ttl):
        # Курса нет или он устарел — обновляем через Parser Service
        _refresh_rates()
        result = _compute_rate(_load_cached_pairs(db), f_code, t_code)

    if result is None:
        raise ValueError(f"Курс для пары {f_code}/{t_code} не найден.")
    return result


def _load_cached_pairs(db: DatabaseManager) -> Dict[str, Any]:
    """Извлекает словарь пар из кэша (новый формат 'pairs' или плоский)."""
    raw = db.load("rates.json", {})
    if not isinstance(raw, dict):
        return {}
    pairs = raw.get("pairs", raw)
    return pairs if isinstance(pairs, dict) else {}


def _is_fresh(updated_at: Optional[str], now: datetime, ttl: int) -> bool:
    if not updated_at:
        return False
    try:
        ts = datetime.fromisoformat(updated_at)
    except (ValueError, TypeError):
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() <= ttl


def _compute_rate(
    rates: Dict[str, Any], f_code: str, t_code: str
) -> Optional[tuple[float, Optional[str], str]]:
    """Прямая пара → обратная пара → кросс-курс через USD."""
    direct = rates.get(f"{f_code}_{t_code}")
    if direct is not None and float(direct.get("rate", 0)) > 0:
        return float(direct["rate"]), direct.get("updated_at"), f"{f_code}_{t_code}"

    reverse = rates.get(f"{t_code}_{f_code}")
    if reverse is not None and float(reverse.get("rate", 0)) > 0:
        return (
            1 / float(reverse["rate"]),
            reverse.get("updated_at"),
            f"{t_code}_{f_code}",
        )

    f_usd = rates.get(f"{f_code}_USD")
    t_usd = rates.get(f"{t_code}_USD")
    if (
        f_usd is not None
        and t_usd is not None
        and float(f_usd.get("rate", 0)) > 0
        and float(t_usd.get("rate", 0)) > 0
    ):
        rate = float(f_usd["rate"]) / float(t_usd["rate"])
        return (
            rate,
            t_usd.get("updated_at"),
            f"{f_code}_{t_code} (кросс-курс через USD)",
        )

    return None

# Публичный алиас для использования из CLI (show-rates --base)
compute_cross_rate = _compute_rate

def _refresh_rates() -> None:
    """Обновляет курсы через Parser Service (CoinGecko + ExchangeRate-API).

    Импорт RatesUpdater ленивый, чтобы не тянуть сетевой слой в каждый
    вызов usecases. Сбой превращается в ApiRequestError для CLI.
    """
    from valutatrade_hub.parser_service.updater import RatesUpdater

    try:
        summary = RatesUpdater().run_update()
    except ApiRequestError:
        raise
    except Exception as exc:  # защита CLI от любых сетевых неожиданностей
        raise ApiRequestError(str(exc)) from exc

    if summary["updated"] == 0:
        raise ApiRequestError(
            "не удалось получить данные ни от одного источника"
        )


def _load_portfolio(db: DatabaseManager, user_id: int) -> tuple[list, Portfolio]:
    """Читает портфель пользователя; запись не найдена — исключение."""
    portfolios = db.load("portfolios.json", [])
    row = next((p for p in portfolios if p["user_id"] == user_id), None)
    if row is None:
        raise ValueError(
            "Портфель пользователя не найден. Зарегистрируйтесь и войдите."
        )
    return portfolios, Portfolio.from_data(row)


def _save_portfolio(
    db: DatabaseManager, portfolios: list, portfolio: Portfolio
) -> None:
    """Чтение → модификация → атомарная запись (обёртка над DatabaseManager)."""
    rows = [p.to_dict() if isinstance(p, Portfolio) else p for p in portfolios]
    for i, p in enumerate(rows):
        if p["user_id"] == portfolio.user_id:
            rows[i] = portfolio.to_dict()
            break
    db.save("portfolios.json", rows)


def show_portfolio(user_id: int, base_currency: str = "USD") -> Dict[str, Any]:
    """Портфель пользователя с конвертацией в базовую валюту (включая кросс-курсы).

    Сумма считается через Portfolio.get_total_value(), строки — циклом поверх.
    """
    db = DatabaseManager()
    portfolios = db.load("portfolios.json", [])
    row = next((p for p in portfolios if p["user_id"] == user_id), None)
    if row is None:
        return {
            "user_id": user_id,
            "wallets": [],
            "total_in_base": 0.0,
            "base_currency": base_currency,
        }

    portfolio = Portfolio.from_data(row)
    base = base_currency.upper()
    items = []
    rates_for_total: Dict[str, float] = {}

    for code, wallet in portfolio.wallets.items():
        if code == base:
            rate = 1.0
        else:
            try:
                rate, _, _ = get_rate(code, base)
            except (ValueError, ApiRequestError):
                rate = 0.0  # нет курса — показываем 0, портфель не падает

        item_value = wallet.balance * rate
        rates_for_total[f"{code}_{base}"] = rate
        items.append(
            {
                "currency_code": code,
                "balance": wallet.balance,
                "value_in_base": item_value,
            }
        )

    return {
        "user_id": user_id,
        "wallets": items,
        "total_in_base": portfolio.get_total_value(base, rates_for_total),
        "base_currency": base,
    }


@log_action(action="BUY")
def buy_currency(user_id: int, currency_code: str, amount: float) -> Dict[str, Any]:
    """Покупает валюту за USD: автосоздание кошелька, списание по курсу."""
    if amount <= 0:
        raise ValueError("Сумма покупки должна быть положительной.")

    currency = get_currency(currency_code.upper())

    db = DatabaseManager()
    portfolios, portfolio = _load_portfolio(db, user_id)

    wallet = portfolio.add_currency(currency.code)
    rate, updated_at, pair = get_rate(currency.code, "USD")
    cost_usd = amount * rate

    usd_wallet = portfolio.add_currency("USD")
    usd_wallet.withdraw(cost_usd)  # InsufficientFundsError при нехватке
    wallet.deposit(amount)

    _save_portfolio(db, portfolios, portfolio)

    return {
        "amount": amount,
        "currency_code": currency.code,
        "rate": rate,
        "cost_usd": cost_usd,
        "updated_at": updated_at,
        "pair": pair,
    }


@log_action(action="SELL")
def sell_currency(user_id: int, currency_code: str, amount: float) -> Dict[str, Any]:
    """Продаёт валюту за USD: списание с кошелька, начисление USD."""
    if amount <= 0:
        raise ValueError("Сумма продажи должна быть положительной.")

    currency = get_currency(currency_code.upper())

    db = DatabaseManager()
    portfolios, portfolio = _load_portfolio(db, user_id)

    wallet = portfolio.get_wallet(currency.code)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька для валюты {currency.code}. Сначала купите её."
        )

    rate, updated_at, pair = get_rate(currency.code, "USD")
    revenue_usd = amount * rate

    wallet.withdraw(amount)  # InsufficientFundsError при нехватке
    portfolio.add_currency("USD").deposit(revenue_usd)

    _save_portfolio(db, portfolios, portfolio)

    return {
        "amount": amount,
        "currency_code": currency.code,
        "rate": rate,
        "revenue_usd": revenue_usd,
        "updated_at": updated_at,
        "pair": pair,
    }
