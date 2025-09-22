import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logging(environment: str | None = None, log_dir: str | None = None, root_level: str | None = None) -> None:
    """
    Configure application-wide logging.

    - Debug/local: logs to stdout
    - Prod: logs to file with 7-day retention (daily rotation)
    """
    env = (environment or "development").lower()
    level_name = (root_level or ("DEBUG" if env in {"dev", "debug", "development", "local"} else "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    # Avoid duplicate handlers if called multiple times
    root_logger = logging.getLogger()
    if getattr(root_logger, "_configured_by_app", False):
        return

    root_logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Ensure no default handlers remain
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    if env in {"prod", "production"}:
        directory = log_dir or "logs"
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception:
            # Fallback to current directory when unable to create directory
            directory = "."

        file_path = os.path.join(directory, "app.log")
        file_handler = TimedRotatingFileHandler(
            filename=file_path,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
            utc=False,
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    # Reduce noisy third-party loggers in production
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "aiogram", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy).setLevel(logging.INFO if env in {"prod", "production"} else logging.DEBUG)

    # Mark configured
    root_logger._configured_by_app = True  # type: ignore[attr-defined]


