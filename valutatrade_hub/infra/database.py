"""Singleton DatabaseManager — абстракция над JSON-хранилищем."""
import json
import os
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Синглтон: единственная точка чтения/записи JSON-файлов.

    Запись выполняется атомарно: сначала во временный файл,
    затем os.replace — так файл не останется «недописанным» при сбое.
    """

    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data_dir = Path(SettingsLoader().get("data_dir"))
            cls._instance._data_dir.mkdir(exist_ok=True)
        return cls._instance

    def load(self, name: str, default=None):
        """Читает data/<name>.json; при отсутствии — возвращает default."""
        path = self._data_dir / name
        if not path.exists():
            return default if default is not None else []
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    def save(self, name: str, data) -> None:
        """Атомарно перезаписывает data/<name>.json."""
        path = self._data_dir / name
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
