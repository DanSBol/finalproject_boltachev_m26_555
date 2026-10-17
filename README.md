# finalproject_boltachev_m26_555

**Valutatrade Hub** — учебный проект: консольный симулятор валютного кошелька.
Реализует регистрацию и вход с хешированием пароля (соль + SHA-256), портфель
с несколькими валютами, покупку и продажу по актуальным курсам, автоматическое
обновление курсов из внешних API и аудит операций в лог-файле.

Проект демонстрирует слоистую архитектуру CLI-приложения (core / infra /
parser_service / cli), работу с JSON-хранилищем, синглтоны, декораторы,
структурированное логирование и контроль качества кода.

---

## 🎯 Цели проекта

- Реализовать полный цикл работы валютного кошелька в CLI: регистрация, вход,
  портфель, покупка и продажа валют по курсу.
- Организовать проект как Python-пакет со слоями: бизнес-логика отделена от
  хранилища, внешних API и интерфейса.
- Обеспечить качество кода через ruff (lint + format) и функциональные тесты.
- Реализовать обновление курсов через внешние API с отказоустойчивостью
  (сбой одного источника не останавливает обновление).

---

## 🛠 Технологии и инструменты

- **Язык:** Python 3.11+
- **Управление зависимостями и виртуальным окружением:** `uv`
- **Контроль качества кода:** `ruff` (lint + format)
- **Тестирование:** `pytest`
- **Вывод таблиц:** `prettytable`
- **Внешние API:** CoinGecko (криптовалюты), ExchangeRate-API (фиат)
- **Хранение данных:** JSON-файлы в папке `data/`
- **Система контроля версий:** Git

---

## 📁 Структура проекта

```text
finalproject_boltachev_m26_555/
├── .venv/                     # Виртуальное окружение (не коммитится)
├── data/                      # Хранилище данных (создаётся автоматически)
│   ├── users.json             # Пользователи (хеш пароля + соль)
│   ├── portfolios.json        # Портфели и балансы
│   ├── rates.json             # Кэш курсов: {"pairs": {...}, "last_refresh": ...}
│   ├── exchange_rates.json    # Журнал истории курсов
│   └── session.json           # Текущая сессия CLI (создаётся при login)
├── logs/                      # Логи (создаётся автоматически)
│   └── actions.log            # Аудит операций (с ротацией)
├── valutatrade_hub/           # Python-пакет
│   ├── cli/
│   │   └── interface.py       # CLI-интерфейс: парсинг аргументов, вывод
│   ├── core/
│   │   ├── models.py          # User, Wallet, Portfolio
│   │   ├── currencies.py      # Иерархия валют (ABC) и реестр
│   │   ├── exceptions.py      # Пользовательские исключения
│   │   └── usecases.py        # Бизнес-логика: register, login, buy, sell...
│   ├── infra/
│   │   ├── database.py        # DatabaseManager (синглтон, атомарная запись)
│   │   └── settings.py        # SettingsLoader (синглтон, pyproject.toml)
│   ├── parser_service/
│   │   ├── api_clients.py     # CoinGeckoClient, ExchangeRateApiClient
│   │   ├── config.py          # ParserConfig (ключ API из .env)
│   │   ├── storage.py         # Кэш rates.json и журнал exchange_rates.json
│   │   └── updater.py         # RatesUpdater: опрос источников, запись кэша
│   ├── decorators.py          # @log_action — аудит доменных операций
│   ├── logging_config.py      # Настройка логирования с ротацией
│   └── tests/
│       └── test_functional.py # Функциональные тесты CLI
├── pyproject.toml             # Метаданные, зависимости, скрипт, ruff
├── uv.lock                    # Lock-файл зависимостей
├── README.md
└── .gitignore
```

## 🚀 Быстрый старт

### Требования

- Python 3.11 или выше
- `uv` (можно установить через `pip install uv`)

### Установка и запуск

1. **Клонирование репозитория** 
(если ещё не сделано):
   ```bash
   git clone https://github.com/DanSBol/finalproject_boltachev_m26_555.git
   cd finalproject_boltachev_m26_555

2. **Создание виртуального окружения и установка зависимостей:**
   ```bash
   uv sync

3. **Проверка качества кода:**
   ```bash
   uv run ruff check .
   uv run ruff format --check .

4. **Запуск CLI:**
   ```bash
   uv run valutatrade-hub --help

(Эквивалентно: uv run python -m valutatrade_hub.cli.interface.)

## 🧪 Основные команды CLI
После запуска модуля доступны следующие команды:
  ```bash
  uv run valutatrade-hub register --username <name> --password <pass>
  uv run valutatrade-hub login --username <name> --password <pass>
  uv run valutatrade-hub logout
  uv run valutatrade-hub show-portfolio [--base <currency>]
  uv run valutatrade-hub buy --currency <code> --amount <value>
  uv run valutatrade-hub sell --currency <code> --amount <value>
  uv run valutatrade-hub get-rate --from <code> --to <code>
  uv run valutatrade-hub update-rates [--source coingecko|exchangerate]
  uv run valutatrade-hub show-rates [--currency <code> | --top N | --base <code>]
  ```
Пример сессии:

  ```bash
  uv run valutatrade-hub register --username Dan --password 1234
  uv run valutatrade-hub login --username Dan --password 1234
  uv run valutatrade-hub get-rate --from EUR --to USD
  uv run valutatrade-hub buy --currency EUR --amount 100
  uv run valutatrade-hub show-portfolio --base USD
  uv run valutatrade-hub sell --currency EUR --amount 40
  uv run valutatrade-hub show-rates --top 2
  uv run valutatrade-hub logout
  ```
⚠️ Для операций buy, sell и show-portfolio требуется предварительно выполнить login. Новому пользователю начисляется стартовый капитал 10 000 USD.

## 💱 Источники курсов
Курсы хранятся в локальном кэше data/rates.json. При обращении к курсу (get-rate, buy, sell, show-portfolio) проверяется свежесть записи по TTL (по умолчанию 60 секунд, настраивается в [tool.valutatrade] в pyproject.toml): устаревший или отсутствующий курс автоматически запрашивается из внешних источников.

- **CoinGecko** — курсы криптовалют к USD (BTC, ETH, SOL).
- **ExchangeRate-API** — курсы фиатных валют (EUR, GBP, RUB) к USD. Ключ читается из переменной окружения EXCHANGERATE_API_KEY или файла .env (не коммитится).

Сбой одного источника логируется, остальные продолжают работу. Поддержаны прямые, обратные и кросс-курсы (через USD): например, EUR→GBP считается как EUR→USD ÷ GBP→USD.

## 📂 Хранение данных
Данные хранятся в JSON-файлах в папке data/; все записи атомарны (сначала временный файл, затем os.replace):

- users.json — пользователи: хеш пароля (SHA-256 с солью), дата регистрации.
- portfolios.json — портфели: баланс по каждой валюте.
- rates.json — срез последних курсов с отметками времени и источником.
- exchange_rates.json — журнал истории курсов (пополняется при каждом обновлении, дубликаты отсекаются по id).
- session.json — текущий пользователь между запусками CLI.

Все файлы создаются автоматически при первом использовании.

## 📜 Логирование
Все ключевые доменные операции (REGISTER, LOGIN, BUY, SELL) пишутся декоратором @log_action в logs/actions.log: метка времени, пользователь, валюта, сумма и вердикт result=OK / result=ERROR с типом исключения. Ротация: файл до 1 МБ, до 5 архивных копий.

## ✅ Контроль качества кода
В проекте настроен ruff для соблюдения стандартов стиля и поиска ошибок:

- Максимальная длина строки: 88 символов.
- Проверка неиспользуемых переменных, синтаксических ошибок, порядка импортов.
- Форматирование через ruff format.

Запуск проверок:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  ```
## 📝 Примечания и ограничения
- Проект учебный: используется файловое хранилище вместо СУБД.
- Пароли хешируются, но проект не предназначен для продакшн-использования.
- Иерархия исключений: все ошибки домена наследуются от ValutatradeError и перехватываются в CLI с понятными сообщениями на русском языке.