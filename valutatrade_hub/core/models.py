"""Модели: User, Wallet, Portfolio. Приватные поля + доступ через свойства."""
import hashlib
import os
from typing import Optional

from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.infra.database import DatabaseManager

SALT_BYTES = 16

class User:
    """Пользователь системы. Все поля приватные, наружу — только свойства."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: str,
    ):
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str):
        if not value or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым.")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        # По заданию нужен геттер, но наружу хеш лучше не отдавать без нужды
        return self._hashed_password

    @staticmethod
    def generate_salt() -> str:
        return os.urandom(SALT_BYTES).hex()

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        pwd_bytes = password.encode("utf-8")
        salt_bytes = bytes.fromhex(salt)
        return hashlib.sha256(pwd_bytes + salt_bytes).hexdigest()

    def change_password(self, new_password: str):
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов.")
        self._salt = self.generate_salt()
        self._hashed_password = self.hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        return self.hash_password(password, self._salt) == self._hashed_password

    def get_user_info(self) -> dict:
        """Публичная информация без пароля."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date,
        }

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date,
        }

    @classmethod
    def from_dict(cls, row: dict) -> "User":
        return cls(
            user_id=row["user_id"],
            username=row["username"],
            hashed_password=row["hashed_password"],
            salt=row["salt"],
            registration_date=row["registration_date"],
        )

    @classmethod
    def load_all_users(cls) -> list["User"]:
        rows = DatabaseManager().load("users.json", [])
        if not isinstance(rows, list):
            return []
        return [cls.from_dict(row) for row in rows]

    @classmethod
    def save_users(cls, users: list["User"]) -> None:
        DatabaseManager().save("users.json", [u.to_dict() for u in users])

    @classmethod
    def find_by_username(cls, username: str) -> Optional["User"]:
        for u in cls.load_all_users():
            if u.username == username:
                return u
        return None

    @classmethod
    def next_user_id(cls) -> int:
        users = cls.load_all_users()
        if not users:
            return 1
        return max(u.user_id for u in users) + 1


class Wallet:
    """Кошелёк одной валюты. Баланс приватный, доступ через deposit/withdraw."""

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code.upper()
        self._balance = float(balance)

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом.")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным.")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной.")
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной.")
        if amount > self._balance:
            raise InsufficientFundsError(
                available=self._balance, required=amount, code=self.currency_code
            )
        self._balance -= amount

    def get_balance_info(self) -> dict:
        return {"currency_code": self.currency_code, "balance": self._balance}


class Portfolio:
    """Портфель: набор кошельков пользователя. Точка интеграции с JSON-хранилищем."""

    def __init__(self, user_id: int):
        self._user_id = user_id
        self._wallets: dict[str, Wallet] = {}

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """Возвращает существующий кошелёк или создаёт пустой (автосоздание в buy)."""
        code = currency_code.upper()
        if code not in self._wallets:
            self._wallets[code] = Wallet(code, 0.0)
        return self._wallets[code]

    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        return self._wallets.get(currency_code.upper())

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "wallets": {code: w.balance for code, w in self._wallets.items()},
        }

    @classmethod
    def from_data(cls, row: dict) -> "Portfolio":
        portfolio = cls(row["user_id"])
        for code, balance in row.get("wallets", {}).items():
            portfolio.add_currency(code).balance = float(balance)
        return portfolio

    def get_total_value(
        self,
        base_currency: str = "USD",
        exchange_rates: dict[str, float] | None = None,
    ) -> float:
        if exchange_rates is None:
            exchange_rates = {}
        base = base_currency.upper()
        total = 0.0
        for code, wallet in self._wallets.items():
            if code == base:
                total += wallet.balance
                continue
            rate = exchange_rates.get(f"{code}_{base}")
            if rate:
                total += wallet.balance * rate
        return total
