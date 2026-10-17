"""Хранилище Parser Service: кэш rates.json и журнал exchange_rates.json."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from valutatrade_hub.parser_service.config import ParserConfig


def _atomic_write(path: Path, data: Any) -> None:
    """Атомарная запись: временный файл → os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _parse_ts(value: Any) -> datetime | None:
    """Парсит ISO-метку времени; None — если распознать не удалось."""
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


class RatesStorage:
    """Работа с двумя хранилищами: снимок курсов и исторический журнал."""

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()

    def load_cache(self) -> dict:
        """Читает rates.json; при отсутствии — пустой словарь."""
        path = Path(self.config.RATES_FILE_PATH)
        if not path.exists():
            return {}
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    def save_cache(self, pairs: dict[str, dict]) -> None:
        """Сохраняет срез последних курсов: {"pairs": {...}, "last_refresh": ...}."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cache = self.load_cache()
        existing = cache.get("pairs", {})
        for pair, entry in pairs.items():
            old = existing.get(pair)
            new_ts = _parse_ts(entry.get("updated_at"))
            old_ts = _parse_ts(old.get("updated_at")) if old else None
            if old is None or (
                new_ts is not None and (old_ts is None or new_ts >= old_ts)
            ):
                existing[pair] = entry
        _atomic_write(
            Path(self.config.RATES_FILE_PATH),
            {"pairs": existing, "last_refresh": now},
        )

    def load_history(self) -> list:
        """Читает журнал exchange_rates.json; при отсутствии — пустой список."""
        path = Path(self.config.HISTORY_FILE_PATH)
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    def append_history(self, records: list[dict]) -> None:
        """Добавляет записи журнала, пропуская дубликаты по id."""
        history = self.load_history()
        seen = {rec["id"] for rec in history}
        for rec in records:
            if rec["id"] not in seen:
                history.append(rec)
        _atomic_write(Path(self.config.HISTORY_FILE_PATH), history)
