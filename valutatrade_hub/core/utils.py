import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DATA_DIR = Path("data")
RATES_FILE = DATA_DIR / "rates.json"
USERS_FILE = DATA_DIR / "users.json"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"

GetRateResult = Tuple[Optional[float], Optional[str], Optional[str]]


def load_json(filename: str) -> Any:
    """
    Загружает JSON из файла в папке data.
    Если файла нет — возвращает пустой список для users/portfolios,
    и пустой dict для остальных (например, rates).
    """
    path = DATA_DIR / filename

    if not path.exists():
        # Для файлов со списками пользователей/портфелей возвращаем пустой список
        if filename in ("users.json", "portfolios.json"):
            return []
        # Для rates.json и других — пустой словарь
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # Если файл битый или нечитаемый — возвращаем безопасное значение
        if filename in ("users.json", "portfolios.json"):
            return []
        return {}


def save_json(filename: str, data: Any) -> None:
    """
    Сохраняет данные в JSON-файл в папке data.
    Папка data создаётся автоматически, если её нет.
    """
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_pair(from_cur: str, to_cur: str) -> str:
    """Приводит пару валют к единому формату: UPPER_UPPER."""
    f = from_cur.strip().upper()
    t = to_cur.strip().upper()
    return f"{f}_{t}"


def load_rates() -> Dict[str, Any]:
    """Загружает курсы из rates.json."""
    if not RATES_FILE.exists():
        return {}
    try:
        with open(RATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}



def get_rate(from_cur: str, to_cur: str) -> GetRateResult:
    """Возвращает (rate, updated_at, pair) или (None, None, None).

    Поддерживает два формата значений в rates.json:
      - словарь: {"rate": 1.1, "updated_at": "..."}
      - число:   1.1 (тогда берём дату из ключа last_refresh файла)
    """
    pair = normalize_pair(from_cur, to_cur)
    reverse_pair = normalize_pair(to_cur, from_cur)

    rates = load_rates()

    file_last_refresh = rates.get("last_refresh") if isinstance(rates, dict) else None

    def extract(pair_name: str):
        """Возвращает (rate, updated_at) для пары в любом формате."""
        if not isinstance(rates, dict) or pair_name not in rates:
            return None, None
        value = rates[pair_name]
        if isinstance(value, dict):
            return value.get("rate"), value.get("updated_at")
        if isinstance(value, (int, float)):
            return value, file_last_refresh
        return None, None

    def is_fresh(updated_at_str: Optional[str]) -> bool:
        if not updated_at_str:
            # Если даты нет вовсе — считаем курс пригодным,
            # иначе ни одна команда не заработает без обновления файла.
            return True
        try:
            if updated_at_str.endswith("Z"):
                updated_at_str = updated_at_str[:-1] + "+00:00"
            last_update = datetime.fromisoformat(updated_at_str)
            if last_update.tzinfo is None:
                now = datetime.now()
                return (now - last_update) < timedelta(minutes=5)
            now = datetime.now(timezone.utc)
            return (now - last_update.astimezone(timezone.utc)) < timedelta(minutes=5)
        except (ValueError, TypeError):
            return False

    # 1. Прямой курс
    rate, updated_at = extract(pair)
    if rate is not None and rate != 0 and is_fresh(updated_at):
        return float(rate), updated_at, pair

    # 2. Обратный курс
    rev_rate, rev_updated_at = extract(reverse_pair)
    if rev_rate is not None and rev_rate != 0 and is_fresh(rev_updated_at):
        return 1.0 / float(rev_rate), rev_updated_at, reverse_pair

    return None, None, None
