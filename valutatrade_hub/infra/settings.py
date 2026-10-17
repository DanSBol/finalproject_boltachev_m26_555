"""Singleton SettingsLoader — единая точка конфигурации проекта.

Выбран способ через __new__: для одного класса он проще и читабельнее,
чем метакласс. Метакласс оправдан, когда синглтонов много или нужна
иерархия таких классов — здесь этого нет.
"""
import tomllib
from pathlib import Path
from typing import Any

DEFAULTS = {
    "data_dir": "data",
    "log_dir": "logs",
    "log_level": "INFO",
    "rates_ttl_seconds": 60,      # политика свежести курсов
    "default_base": "USD",        # дефолтная базовая валюта
}


class SettingsLoader:
    """Синглтон: в приложении существует ровно один экземпляр."""

    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._reload()
        return cls._instance

    def _reload(self) -> None:
        self._values = dict(DEFAULTS)
        # Секция [tool.valutatrade] в pyproject.toml переопределяет дефолты
        pyproject = Path("pyproject.toml")
        if pyproject.exists():
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            self._values.update(data.get("tool", {}).get("valutatrade", {}))

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def reload(self) -> None:
        """Перезагрузить конфигурацию с диска."""
        self._reload()
