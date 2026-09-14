"""Реэкспорт логирования из shared."""
from shared.logger import get_payment_logger, setup_logging

__all__ = ["setup_logging", "get_payment_logger"]
