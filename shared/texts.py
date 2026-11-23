"""Локальные тексты бота: texts.toml (вне git) с запасным texts.example.toml.

Путь к основному файлу: env TEXTS_FILE или <корень проекта>/texts.toml
(в контейнере /app/texts.toml, монтируется из хоста). Никогда не падает:
при отсутствии файла/ключа пишет в лог и берёт нейтральный текст из шаблона.
"""

import logging
import os
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_EXAMPLE = Path(__file__).with_name("texts.example.toml")
_DEFAULT_MAIN = Path(__file__).resolve().parent.parent / "texts.toml"


def _load(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        logger.warning("texts: файл %s не найден", path)
    except (tomllib.TOMLDecodeError, OSError):
        logger.exception("texts: не удалось прочитать %s", path)
    return {}


_main: dict[str, Any] | None = None
_example: dict[str, Any] | None = None


def _data() -> tuple[dict[str, Any], dict[str, Any]]:
    global _main, _example
    if _main is None:
        _main = _load(Path(os.environ.get("TEXTS_FILE") or _DEFAULT_MAIN))
        _example = _load(_EXAMPLE)
    return _main, _example or {}


def reload() -> None:
    global _main, _example
    _main = _example = None


def get(key: str, default: Any = None) -> Any:
    """Значение по ключу вида 'section.sub'. Фолбэк: шаблон, затем default."""
    main, example = _data()
    for src, name in ((main, "texts.toml"), (example, "texts.example.toml")):
        cur: Any = src
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                cur = None
                break
            cur = cur[part]
        if cur is not None:
            if name != "texts.toml":
                logger.error("texts: ключ %r отсутствует в texts.toml, взят из шаблона", key)
            return cur
    logger.error("texts: ключ %r не найден нигде, default", key)
    return default


def professions() -> list[dict[str, Any]]:
    """Список профессий для сидирования БД."""
    value = get("professions", [])
    return value if isinstance(value, list) else []
