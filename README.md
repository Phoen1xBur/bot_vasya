# Бот Вася

Telegram-бот с WebApp на FastAPI, SQLAlchemy, Alembic, Redis и распознаванием речи Vosk.

## Стек
- aiogram 3 (бот), Pyrogram клиент
- FastAPI + Uvicorn
- SQLAlchemy 2 (async) + Alembic
- Redis
- Vosk (speech-to-text)

## Быстрый старт
1. Создайте и заполните `.env` (см. ниже)
2. Установите зависимости:
```bash
pip install -r requirements.txt
```
3. Примените миграции:
```bash
alembic upgrade head
```
4. Запустите приложение:
```bash
python -m src.run
```

Бот (polling), API и фоновый чистильщик сообщений запускаются вместе.

## Переменные окружения (.env)
Минимальный набор:
```
TOKEN=xxxx
API_ID=xxxx
API_HASH=xxxx
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bot_vasya
DB_USER=postgres
DB_PASS=postgres
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
ENABLE_VOICE=false

# Логирование/конфиг
ENV=development   # development | production
LOG_DIR=logs      # папка для логов в проде
# LOG_LEVEL=DEBUG # необязательная переопределяемая настройка уровня
```

## Логирование
Централизованное логирование настроено в `src/utils/logger.py` и подключается в `src/run.py`.
- Development (`ENV=development`):
  - Уровень: DEBUG по умолчанию
  - Вывод: консоль (stdout)
- Production (`ENV=production`):
  - Уровень: INFO по умолчанию
  - Вывод: файл с ротацией `LOG_DIR/app.log`
  - Ротация: ежедневно в полночь
  - Хранение: 7 дней (backupCount=7)

Чтобы явно задать уровень логирования, используйте `LOG_LEVEL` (например, `DEBUG`, `INFO`).

## API
FastAPI по умолчанию доступен на `http://127.0.0.1:8000`.
- Статика WebApp монтируется по пути `/webapp`, если существует `src/webapp/static`.
- Роуты: `user`, `casino` (авторизация через Telegram init data в заголовке).

## Разработка
- Форматирование/линтинг: рекомендуется black/ruff/mypy (пока не принудительно).
- Миграции: стандартный Alembic workflow.
- Секреты: храните только в переменных окружения.

## Примечания
- Большие файлы (например, модели Vosk) лучше не коммитить — используйте внешнее хранилище или Git LFS.
- CORS по умолчанию открыт; в продакшене ограничьте доверенные источники.
