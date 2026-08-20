"""
Тесты Pydantic моделей: ChatRequest и ChatResponse.

Проверяют:
- Корректное создание валидных объектов
- Валидацию входных данных (min/max длина, None)
- Обработку пробелов
- Конвертацию модели в словарь (model_dump)
"""
import pytest
from llm.schemas import ChatRequest, ChatResponse


class TestChatRequest:
    """Тесты модели ChatRequest — входной запрос к /chat endpoint."""

    def test_valid_request(self):
        """Создание валидного запроса с нормальным сообщением."""
        req = ChatRequest(message="Привет")
        assert req.message == "Привет"

    def test_message_stripped(self):
        """Проверяет, что пробелы вокруг сообщения обрезаются."""
        req = ChatRequest(message="  Привет  ")
        assert req.message == "Привет"

    def test_message_whitespace_only(self):
        """Проверяет, что сообщение из пробелов вызывает ошибку валидации."""
        with pytest.raises(ValueError, match="Сообщение не может быть пустым или состоять только из пробелов"):
            ChatRequest(message="   ")

    def test_message_too_long(self):
        """Проверяет, что сообщение длиннее 1000 символов вызывает ValueError."""
        with pytest.raises(ValueError, match="Сообщение слишком длинное"):
            ChatRequest(message="x" * 1001)

    def test_empty_message(self):
        """Проверяет, что пустое сообщение вызывает ValueError."""
        with pytest.raises(ValueError, match="Сообщение не может быть пустым"):
            ChatRequest(message="")


class TestChatResponse:
    """Тесты модели ChatResponse — ответ от сервиса."""

    def test_valid_response(self):
        """Создание валидного ответа с текстом reply."""
        resp = ChatResponse(reply="Ответ ассистента")
        assert resp.reply == "Ответ ассистента"

    def test_response_to_dict(self):
        """Конвертация модели в dict через model_dump()."""
        resp = ChatResponse(reply="Hello")
        d = resp.model_dump()
        assert d == {"reply": "Hello", "generation_mode": "llm"}

    def test_response_with_fallback_mode(self):
        """Создание ответа с generation_mode=fallback."""
        resp = ChatResponse(reply="Fallback", generation_mode="fallback")
        assert resp.generation_mode == "fallback"
