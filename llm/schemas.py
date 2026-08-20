"""
Модели данных (DTO) для взаимодействия с LLM-клиентом и API.

Этот модуль содержит все Pydantic-модели и константы, используемые
между слоями LLMClient и ChatService, чтобы избежать циклической зависимости
между llm/ и services/.
"""
# no additional imports needed

from pydantic import BaseModel, Field, field_validator


class ChatServiceError(Exception):
    """Ошибка инициализации сервиса (например, LLM-клиент не настроен)."""



class ChatRequest(BaseModel):
    """Валидированный запрос от /api/chat."""
    message: str = Field(..., description="Сообщение пользователя")

    @field_validator("message")
    @classmethod
    def validate_and_normalize_message(cls, v: str) -> str:
        """
        Валидация и нормализация сообщения.

        Проверяет:
        1. Не пуста ли строка после strip()
        2. Длина в допустимых пределах (1-1000 символов)
        """
        stripped = v.strip()
        if not stripped:
            raise ValueError("Сообщение не может быть пустым или состоять только из пробелов")
        if len(stripped) < 1:
            raise ValueError("Сообщение не может быть пустым")
        if len(stripped) > 1000:
            raise ValueError("Сообщение слишком длинное (максимум 1000 символов)")
        return stripped


class ChatResponse(BaseModel):
    """Ответ от LLM-сервиса."""
    reply: str
    generation_mode: str = "llm"


SYSTEM_PROMPT = (
    "Ты — полезный ассистент. Отвечай кратко и по существу. "
    "Если не уверен в ответе, честно скажи об этом."
)
