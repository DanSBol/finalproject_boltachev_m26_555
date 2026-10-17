"""CLI-интерфейс valutatrade_hub."""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from prettytable import PrettyTable

from valutatrade_hub.core.currencies import SUPPORTED_CURRENCIES
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import (
    buy_currency,
    compute_cross_rate,
    get_rate,
    login_user,
    register_user,
    sell_currency,
    show_portfolio,
)
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import configure_logging
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.updater import RatesUpdater

SESSION_FILE = Path(SettingsLoader().get("data_dir", "data")) / "session.json"

# Глобальная сессия: данные текущего пользователя после login
current_user: Optional[Dict[str, Any]] = None


def _save_session(user_data: Dict[str, Any]) -> None:
    SESSION_FILE.parent.mkdir(exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)


def _load_session() -> None:
    global current_user
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                current_user = json.load(f)
        except (json.JSONDecodeError, IOError):
            current_user = None
    else:
        current_user = None


def _require_session() -> None:
    _load_session()
    if current_user is None:
        print("Сначала выполните login")
        sys.exit(1)


def _cli_log(func):
    """Декоратор CLI-команд: метка времени и результат в stdout."""
    from datetime import datetime, timezone

    def wrapper(*args, **kwargs):
        cmd_name = func.__name__.replace("_", "-")
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            result = func(*args, **kwargs)
            print(f"[LOG] {timestamp} | {cmd_name} | SUCCESS")
            return result
        except SystemExit:
            print(f"[LOG] {timestamp} | {cmd_name} | ERROR")
            raise
        except Exception as e:
            print(f"[LOG] {timestamp} | {cmd_name} | ERROR: {e}")
            raise

    return wrapper


@_cli_log
def cmd_register(args: argparse.Namespace):
    try:
        user = register_user(username=args.username, password=args.password)
        print(
            f"Пользователь '{user['username']}' зарегистрирован "
            f"(id={user['user_id']}).\n"
            "Войдите: login --username <имя> --password <пароль>"
        )
    except ValueError as e:
        print(f"Ошибка регистрации: {e}")
        sys.exit(1)


@_cli_log
def cmd_login(args: argparse.Namespace):
    global current_user
    try:
        current_user = login_user(
            username=args.username,
            password=args.password,
        )
        _save_session(current_user)
        print(
            f"Вы вошли как '{current_user['username']}' "
            f"(id={current_user['user_id']})"
        )
    except ValueError as e:
        print(f"Ошибка входа: {e}")
        sys.exit(1)


@_cli_log
def cmd_logout(args: argparse.Namespace):
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
        print("Вы вышли из системы.")
    else:
        print("Вы и так не вошли.")


@_cli_log
def cmd_show_portfolio(args: argparse.Namespace):
    _require_session()

    base_currency = (
        args.base.upper() if args.base
        else SettingsLoader().get("default_base", "USD")
    )

    try:
        data = show_portfolio(
            user_id=current_user["user_id"],
            base_currency=base_currency,
        )
    except Exception as e:
        print(f"Ошибка при получении портфеля: {e}")
        sys.exit(1)

    wallets = data.get("wallets", [])
    total_in_base = data.get("total_in_base", 0.0)
    base = data.get("base_currency", "USD")

    if not wallets:
        print(f"У пользователя '{current_user['username']}' нет кошельков.")
        return

    table = PrettyTable()
    table.field_names = ["Валюта", "Баланс", f"Стоимость в {base}"]
    table.align["Валюта"] = "l"
    table.align["Баланс"] = "r"
    table.align[f"Стоимость в {base}"] = "r"

    for w in wallets:
        table.add_row(
            [w["currency_code"], f"{w['balance']:.4f}", f"{w['value_in_base']:.2f}"]
        )

    print(f"\nПортфель пользователя '{current_user['username']}' (база: {base}):")
    print(table)
    print("-" * 40)
    print(f"ИТОГО: {total_in_base:.2f} {base}")


@_cli_log
def cmd_buy(args: argparse.Namespace):
    _require_session()

    if args.amount <= 0:
        print("Ошибка: amount должен быть положительным числом.")
        sys.exit(1)

    try:
        res = buy_currency(
            user_id=current_user["user_id"],
            currency_code=args.currency.upper(),
            amount=args.amount,
        )
        print(
            f"Покупка выполнена: {res['amount']:.4f} {res['currency_code']} "
            f"по курсу {res['rate']:.4f} USD/единицу.\n"
            f"Стоимость покупки: {res['cost_usd']:.2f} USD"
        )
    except InsufficientFundsError as e:
        print(f"Ошибка покупки: {e}")
        sys.exit(1)
    except CurrencyNotFoundError as e:
        codes = ", ".join(sorted(SUPPORTED_CURRENCIES))
        print(f"Ошибка покупки: {e}")
        print(f"Поддерживаемые коды: {codes}")
        sys.exit(1)
    except ValueError as e:
        print(f"Ошибка покупки: {e}")
        sys.exit(1)


@_cli_log
def cmd_sell(args: argparse.Namespace):
    _require_session()

    if args.amount <= 0:
        print("Ошибка: amount должен быть положительным числом.")
        sys.exit(1)

    try:
        res = sell_currency(
            user_id=current_user["user_id"],
            currency_code=args.currency.upper(),
            amount=args.amount,
        )
        print(
            f"Продажа выполнена: {res['amount']:.4f} {res['currency_code']} "
            f"по курсу {res['rate']:.4f} USD/единицу.\n"
            f"Выручка: {res['revenue_usd']:.2f} USD"
        )
    except InsufficientFundsError as e:
        print(f"Ошибка продажи: {e}")
        sys.exit(1)
    except CurrencyNotFoundError as e:
        codes = ", ".join(sorted(SUPPORTED_CURRENCIES))
        print(f"Ошибка продажи: {e}")
        print(f"Поддерживаемые коды: {codes}")
        sys.exit(1)
    except ValueError as e:
        print(f"Ошибка продажи: {e}")
        sys.exit(1)


@_cli_log
def cmd_get_rate(args: argparse.Namespace):
    from_cur = args.from_currency.strip().upper()
    to_cur = args.to_currency.strip().upper()

    try:
        rate, updated, pair = get_rate(from_cur, to_cur)
        print(f"\nКурс {pair}: {rate:.6f}")
        if updated:
            print(f"Обновлено: {updated}")
        print("-" * 30)
    except CurrencyNotFoundError as e:
        codes = ", ".join(sorted(SUPPORTED_CURRENCIES))
        print(e)
        print(f"Поддерживаемые коды: {codes}. Подробнее: help get-rate")
        sys.exit(1)
    except ApiRequestError:
        print("Сервис курсов недоступен. Проверьте сеть и попробуйте позже.")
        sys.exit(1)
    except ValueError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


@_cli_log
def cmd_update_rates(args: argparse.Namespace):
    """Немедленное обновление курсов через Parser Service."""
    print("INFO: Starting rates update...")
    try:
        summary = RatesUpdater().run_update(source=args.source)
    except ApiRequestError as e:
        print(f"ERROR: {e}")
        print("Update failed. Check logs/actions.log for details.")
        sys.exit(1)

    for error in summary["errors"]:
        print(f"ERROR: {error}")

    if summary["updated"] == 0:
        print("Update completed with errors. Check logs/actions.log for details.")
        sys.exit(1)

    print(
        f"Update successful. Total rates updated: {summary['updated']}. "
        f"Last refresh: {summary['last_refresh']}"
    )


@_cli_log
def cmd_show_rates(args: argparse.Namespace):
    """Показать курсы из локального кеша с фильтрацией."""
    db = DatabaseManager()
    cache = db.load("rates.json", {})
    pairs = cache.get("pairs", cache) if isinstance(cache, dict) else {}
    pairs = {p: e for p, e in pairs.items() if isinstance(e, dict)}

    if not pairs:
        print(
            "Локальный кеш курсов пуст. "
            "Выполните 'update-rates', чтобы загрузить данные."
        )
        sys.exit(1)

    if args.currency:
        code = args.currency.strip().upper()
        pairs = {p: e for p, e in pairs.items() if code in p.split("_")}
        if not pairs:
            print(f"Курс для '{args.currency}' не найден в кеше.")
            sys.exit(1)
    elif args.top:
        crypto = ParserConfig.CRYPTO_CURRENCIES
        usd_pairs = {
            p: e for p, e in pairs.items()
            if p.split("_")[0] in crypto and p.split("_")[1] == "USD"
        }
        ranked = sorted(usd_pairs.items(), key=lambda kv: kv[1]["rate"], reverse=True)
        pairs = dict(ranked[: args.top])
        if not pairs:
            print("В кеше нет курсов криптовалют. Выполните 'update-rates'.")
            sys.exit(1)
    elif args.base:
        pairs = _recompute_against_base(pairs, args.base.strip().upper())
        if not pairs:
            print(
                f"Не удалось рассчитать курсы относительно {args.base.strip().upper()}."
            )
            sys.exit(1)

    last_refresh = cache.get("last_refresh", "") if isinstance(cache, dict) else ""
    print(f"\nRates from cache (updated at {last_refresh}):")
    table = PrettyTable()
    table.field_names = ["Пара", "Курс", "Источник"]
    for pair, entry in sorted(pairs.items()):
        table.add_row([pair, f"{entry['rate']:.6f}", entry.get("source", "")])
    print(table)


def _recompute_against_base(pairs: Dict[str, Any], base: str) -> Dict[str, Any]:
    """Пересчитывает курсы кэша относительно указанной базовой валюты."""
    recomputed: Dict[str, Any] = {}
    for f_code in sorted({p.split("_")[0] for p in pairs}):
        if f_code == base:
            continue
        result = compute_cross_rate(pairs, f_code, base)
        if result:
            recomputed[f"{f_code}_{base}"] = {
                "rate": result[0],
                "updated_at": result[1],
                "source": "кросс-курс",
            }
    return recomputed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="valutatrade-hub",
        description="Консольный симулятор валютного кошелька",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_reg = subparsers.add_parser(
        "register", help="Зарегистрировать нового пользователя"
    )
    p_reg.add_argument("--username", required=True, help="Имя пользователя")
    p_reg.add_argument(
        "--password", required=True, help="Пароль (не менее 4 символов)"
    )
    p_reg.set_defaults(func=cmd_register)

    p_login = subparsers.add_parser("login", help="Войти в систему")
    p_login.add_argument("--username", required=True, help="Имя пользователя")
    p_login.add_argument("--password", required=True, help="Пароль")
    p_login.set_defaults(func=cmd_login)

    p_logout = subparsers.add_parser("logout", help="Выйти из системы")
    p_logout.set_defaults(func=cmd_logout)

    p_port = subparsers.add_parser(
        "show-portfolio", help="Показать портфель пользователя"
    )
    p_port.add_argument(
        "--base",
        default=SettingsLoader().get("default_base", "USD"),
        help="Базовая валюта конвертации",
    )
    p_port.set_defaults(func=cmd_show_portfolio)

    p_buy = subparsers.add_parser("buy", help="Купить валюту")
    p_buy.add_argument("--currency", required=True, help="Код валюты (например, BTC)")
    p_buy.add_argument(
        "--amount", type=float, required=True, help="Количество валюты"
    )
    p_buy.set_defaults(func=cmd_buy)

    p_sell = subparsers.add_parser("sell", help="Продать валюту")
    p_sell.add_argument("--currency", required=True, help="Код валюты")
    p_sell.add_argument(
        "--amount", type=float, required=True, help="Количество валюты"
    )
    p_sell.set_defaults(func=cmd_sell)

    p_rate = subparsers.add_parser("get-rate", help="Получить курс валюты")
    p_rate.add_argument(
        "--from", dest="from_currency", required=True, help="Валюта источника"
    )
    p_rate.add_argument(
        "--to", dest="to_currency", required=True, help="Целевая валюта"
    )
    p_rate.set_defaults(func=cmd_get_rate)

    p_upd = subparsers.add_parser(
        "update-rates", help="Обновить курсы из внешних API"
    )
    p_upd.add_argument(
        "--source",
        choices=["coingecko", "exchangerate"],
        default=None,
        help="Обновить только из указанного источника",
    )
    p_upd.set_defaults(func=cmd_update_rates)

    p_show = subparsers.add_parser(
        "show-rates", help="Показать курсы из локального кеша"
    )
    p_show.add_argument("--currency", default=None, help="Фильтр по валюте")
    p_show.add_argument(
        "--top", type=int, default=None, help="N самых дорогих криптовалют"
    )
    p_show.add_argument(
        "--base", default=None, help="Показать курсы относительно базы"
    )
    p_show.set_defaults(func=cmd_show_rates)

    return parser


def main():
    settings = SettingsLoader()
    configure_logging(
        level=settings.get("log_level", "INFO"),
        log_dir=settings.get("log_dir", "logs"),
    )
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
