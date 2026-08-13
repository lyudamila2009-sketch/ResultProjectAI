"""
Тесты Pydantic моделей: ChatRequest и ChatResponse.

Проверяют:
- Корректное создание валидных объектов
- Валидацию входных данных (min/max длина, None)
- Конвертацию модели в словарь (model_dump)
"""
import pytest
from services.chat import ChatRequest, ChatResponse


class TestChatRequest:
    """Тесты модели ChatRequest — входной запрос к /chat endpoint."""

    def test_valid_request(self):
        """Создание валидного запроса с нормальным сообщением."""
        req = ChatRequest(message="Привет")
        assert req.message == "Привет"

    def test_message_too_long(self):
        """Проверяет, что сообщение длиннее 1000 символов вызывает ValueError."""
        with pytest.raises(ValueError):
            ChatRequest(message="x" * 1001)

    def test_empty_message(self):
        """Проверяет, что пустое сообщение вызывает ValueError (min_length=1)."""
        with pytest.raises(ValueError):
            ChatRequest(message="")

    def test_none_message(self):
        """Проверяет, что None вызывает ValueError (поле обязательное)."""
        with pytest.raises(ValueError):
            ChatRequest(message=None)


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
        assert d == {"reply": "Hello"}
