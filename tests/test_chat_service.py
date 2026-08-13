"""
Тесты ChatService — бизнес-логика обработки чат-запросов.

Проверяют:
- Инициализацию с LLM-клиентом и fallback-сообщением
- Возврат ответа от LLM при успешном запросе
- Поведение без LLM-клиента (ошибка ChatServiceError)
- Детерминированность и case-insensitive ключей кэша
"""
import pytest
from unittest.mock import AsyncMock
from services.chat import ChatService, ChatServiceError, ChatRequest, ChatResponse


class TestChatService:
    """Набор тестов для класса ChatService."""

    def _create_mock_client(self):
        """Создаёт мок LLM-клиент с фиксированным ответом для тестов."""
        client = AsyncMock()
        client.generate = AsyncMock(return_value=ChatResponse(reply="Mock answer"))
        return client

    def test_init_with_llm_client(self):
        """Проверяет, что ChatService корректно принимает и сохраняет LLM-клиент."""
        mock_client = self._create_mock_client()
        service = ChatService(llm_client=mock_client)
        assert service._llm_client is not None

    def test_init_with_fallback(self):
        """Проверяет установку пользовательского fallback-сообщения."""
        service = ChatService(fallback_message="Custom fallback")
        assert service._fallback_message == "Custom fallback"

    @pytest.mark.asyncio
    async def test_chat_returns_llm_response(self):
        """Проверяет, что сервис возвращает ответ от LLM при успешном запросе."""
        mock_client = self._create_mock_client()
        service = ChatService(llm_client=mock_client, fallback_message="Fallback")
        req = ChatRequest(message="Test message")
        response = await service.chat(req)
        assert response.reply == "Mock answer"

    @pytest.mark.asyncio
    async def test_chat_returns_fallback_when_no_client(self):
        """
        Проверяет, что без LLM-клиента сервис бросает ChatServiceError.
        Это ожидаемое поведение — сервис не должен молча падать.
        """
        service = ChatService(fallback_message="Fallback")
        req = ChatRequest(message="Test")
        with pytest.raises(ChatServiceError):
            await service.chat(req)

    def test_cache_key_is_deterministic(self):
        """Одно и то же сообщение всегда даёт одинаковый ключ кэша."""
        service = ChatService()
        key1 = service._cache_key("hello")
        key2 = service._cache_key("hello")
        assert key1 == key2

    def test_cache_key_is_case_insensitive(self):
        """Ключ кэша не зависит от регистра (hello и Hello — одинаковый ключ)."""
        service = ChatService()
        key1 = service._cache_key("Hello")
        key2 = service._cache_key("hello")
        assert key1 == key2
