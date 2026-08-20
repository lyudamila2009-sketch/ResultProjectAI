"""
Correlation ID для отслеживания запросов.

Использует contextvars для хранения request_id в рамках обработки
одного запроса. Автоматически передаётся в handler-логи.
"""
import logging
import uuid
from contextvars import ContextVar
from typing import Optional

# Текущий request_id в рамках обработки запроса
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Получить текущий request_id."""
    return _request_id.get()


def set_request_id(value: Optional[str]) -> None:
    """Установить текущий request_id."""
    _request_id.set(value)


def generate_request_id() -> str:
    """Сгенерировать новый UUID для запроса."""
    return str(uuid.uuid4())


class RequestIdFilter(logging.Filter):
    """Фильтр, который подставляет request_id в запись лога."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Подставить request_id из контекста."""
        record.request_id = get_request_id()
        return True


def setup_request_id_logging() -> RequestIdFilter:
    """
    Настроить подстановку request_id во все логи.

    Returns:
        RequestIdFilter для добавления в корневой логгер.
    """
    request_id_filter = RequestIdFilter()
    logging.getLogger().addFilter(request_id_filter)
    return request_id_filter
