"""
Настройка структурированного JSON-логирования.

Все логи выводятся в stdout в формате JSON для парсинга и агрегации.
"""
import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    """JSON-форматтер для структурированного логирования."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Сформировать JSON-строку из записи лога.

        Args:
            record: запись лога.

        Returns:
            JSON-строка.
        """
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "line": record.lineno,
        }

        # request_id — из контекста
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_data["request_id"] = request_id

        # Дополнительные поля из extra (record.exc_info)
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    """
    Настроить JSON-логирование для корневых логгеров.

    Args:
        level: уровень логирования.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Очистить предыдущие handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
