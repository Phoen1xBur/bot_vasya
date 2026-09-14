"""Централизованное логирование.

Development — DEBUG в консоль; Production — INFO в файл с ротацией.
Отдельный логгер платежей — для аудита.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logging(env: str = "development", log_dir: str = "logs", log_level: str | None = None) -> None:
    level = log_level or ("DEBUG" if env == "development" else "INFO")
    root = logging.getLogger()
    root.setLevel(level)

    # Чистим старые хендлеры (повторные вызовы в тестах)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    if env == "production":
        os.makedirs(log_dir, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(level)
        root.addHandler(file_handler)

    # Отдельный логгер платежей
    pay_logger = logging.getLogger("payments")
    if env == "production":
        os.makedirs(log_dir, exist_ok=True)
        pay_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, "payments.log"),
            when="midnight",
            backupCount=30,
            encoding="utf-8",
        )
        pay_handler.setFormatter(fmt)
        pay_logger.addHandler(pay_handler)
    pay_logger.propagate = True


def get_payment_logger() -> logging.Logger:
    return logging.getLogger("payments")
