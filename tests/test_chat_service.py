"""
Тесты ChatService — бизнес-логика обработки чат-запросов.

Проверяют:
- Инициализацию с LLM-клиентом и fallback-сообщением
- Возврат ответа от LLM при успешном запросе
- Поведение без LLM-клиента (ошибка ChatServiceError)
- Детерминированность ключа кэша
- Fallback при недоступности LLM
- TTL кэша
- Case-sensitive ключи кэша
- Однократный вызов LLM при повторных запросах
- Восстановление кэша из файла
- Обработка повреждённого файла кэша
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock
from services.chat import ChatService, ChatServiceError, ChatRequest, ChatResponse


class TestChatService:
    """Набор тестов для класса ChatService."""

    def _create_mock_client(self):
        """Создаёт мок LLM-клиент с фиксированным ответом для тестов."""
        client = AsyncMock()
        client.generate = AsyncMock(return_value=ChatResponse(reply="Mock answer"))
        return client

    def _default_cache_path(self, tmp_path: Path) -> Path:
        """Утилита для создания изолированного пути кэша."""
        return tmp_path / "test_cache.json"

    def test_init_with_llm_client(self, tmp_path):
        """Проверяет, что ChatService корректно принимает и сохраняет LLM-клиент."""
        mock_client = self._create_mock_client()
        service = ChatService(
            llm_client=mock_client,
            cache_path=self._default_cache_path(tmp_path),
        )
        assert service._llm_client is not None

    def test_init_with_fallback(self, tmp_path):
        """Проверяет установку пользовательского fallback-сообщения."""
        service = ChatService(
            fallback_message="Custom fallback",
            cache_path=self._default_cache_path(tmp_path),
        )
        assert service._fallback_message == "Custom fallback"

    @pytest.mark.asyncio
    async def test_chat_returns_llm_response(self, tmp_path):
        """Проверяет, что сервис возвращает ответ от LLM при успешном запросе."""
        mock_client = self._create_mock_client()
        service = ChatService(
            llm_client=mock_client,
            fallback_message="Fallback",
            cache_path=self._default_cache_path(tmp_path),
        )
        req = ChatRequest(message="Test message")
        response = await service.chat(req)
        assert response.reply == "Mock answer"

    @pytest.mark.asyncio
    async def test_chat_raises_error_when_no_client(self, tmp_path):
        """
        Проверяет, что без LLM-клиента сервис бросает ChatServiceError.
        Fallback срабатывает только когда LLM-клиент есть, но выдаёт исключение.
        Если клиента нет вообще — это ошибка конфигурации.
        """
        service = ChatService(
            fallback_message="Fallback",
            cache_path=self._default_cache_path(tmp_path),
        )
        req = ChatRequest(message="Test")
        with pytest.raises(ChatServiceError):
            await service.chat(req)

    @pytest.mark.asyncio
    async def test_generate_called_once_on_duplicate_request(self, tmp_path):
        """
        Проверяет, что при повторном запросе LLM-клиент вызывается ровно один раз.
        Второй запрос должен вернуться из кэша.
        """
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=ChatResponse(reply="Answer"))
        service = ChatService(
            llm_client=mock_client,
            fallback_message="Fallback",
            cache_path=self._default_cache_path(tmp_path),
        )
        req = ChatRequest(message="Hello")

        # Первый запрос — вызов LLM
        await service.chat(req)
        assert mock_client.generate.call_count == 1

        # Второй запрос — из кэша
        await service.chat(req)
        assert mock_client.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_disk_write_and_read(self, tmp_path):
        """
        Проверяет, что ответ записывается на диск и восстанавливается
        после создания нового экземпляра сервиса.
        """
        cache_file = tmp_path / "chat_cache.json"
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=ChatResponse(reply="DiskAnswer"))
        service = ChatService(
            llm_client=mock_client,
            fallback_message="Fallback",
            cache_path=cache_file,
            model_name="TestModel",
        )
        req = ChatRequest(message="disk test")

        # Запись
        await service.chat(req)
        assert mock_client.generate.call_count == 1
        assert cache_file.exists()

        # Восстановление: создаём новый сервис, загружающий кэш с диска
        service2 = ChatService(
            llm_client=AsyncMock(),
            fallback_message="Fallback",
            cache_path=cache_file,
            model_name="TestModel",
        )
        resp = await service2.chat(req)

        # Должен прийти ответ из кэша, а не из нового LLM
        assert resp.reply == "DiskAnswer"
        assert resp.generation_mode == "cache"
        service2._llm_client.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_recover_from_corrupted_file(self, tmp_path):
        """
        Проверяет, что сервис корректно обрабатывает повреждённый файл кэша:
        запускается и использует fallback при запросе.
        """
        cache_file = tmp_path / "chat_cache.json"
        cache_file.write_text("{broken json content", encoding="utf-8")

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=ChatResponse(reply="FallbackAnswer"))
        service = ChatService(
            llm_client=mock_client,
            fallback_message="Fallback",
            cache_path=cache_file,
            model_name="TestModel",
        )
        req = ChatRequest(message="corrupted")
        resp = await service.chat(req)

        assert resp.reply == "FallbackAnswer"
        assert resp.generation_mode == "llm"

    def test_cache_key_is_deterministic(self):
        """Одно и то же сообщение всегда даёт одинаковый ключ кэша."""
        service = ChatService()
        key1 = service._cache_key("hello")
        key2 = service._cache_key("hello")
        assert key1 == key2

    def test_cache_key_is_case_sensitive(self):
        """Ключ кэша чувствителен к регистру (Hello и hello — разные ключи)."""
        service = ChatService()
        key1 = service._cache_key("Hello")
        key2 = service._cache_key("hello")
        assert key1 != key2

    def test_cache_key_includes_model(self):
        """Ключ кэша зависит от имени модели."""
        service1 = ChatService(model_name="ModelA")
        service2 = ChatService(model_name="ModelB")
        key1 = service1._cache_key("hello")
        key2 = service2._cache_key("hello")
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_chat_returns_fallback_on_llm_error(self, tmp_path):
        """
        Проверяет, что при ошибке LLM возвращается fallback-ответ
        с generation_mode="fallback" вместо ChatServiceError.
        """
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=Exception("Connection error"))
        service = ChatService(
            llm_client=mock_client,
            fallback_message="Fallback",
            cache_path=self._default_cache_path(tmp_path),
        )
        req = ChatRequest(message="Test")
        response = await service.chat(req)
        assert response.reply == "Fallback"
        assert response.generation_mode == "fallback"

    def test_cache_ttl_default(self, tmp_path):
        """Проверяет, что TTL кэша по умолчанию равен 3600."""
        service = ChatService(cache_path=self._default_cache_path(tmp_path))
        assert service._cache_ttl == 3600

    def test_validate_cache_value_valid(self):
        """Валидная запись кэша проходит проверку."""
        service = ChatService()
        assert service._validate_cache_value({"reply": "text", "created_at": 1.0}) is True

    def test_validate_cache_value_missing_fields(self):
        """Запись без required полей не проходит проверку."""
        service = ChatService()
        assert service._validate_cache_value({"reply": "text"}) is False
        assert service._validate_cache_value({"created_at": 1.0}) is False

    def test_validate_cache_value_wrong_types(self):
        """Запись с неверными типами полей не проходит проверку."""
        service = ChatService()
        assert service._validate_cache_value({"reply": 123, "created_at": 1.0}) is False
        assert service._validate_cache_value({"reply": "text", "created_at": "bad"}) is False

    def test_validate_cache_value_not_dict(self):
        """Не-dict значения не проходят проверку."""
        service = ChatService()
        assert service._validate_cache_value([]) is False
        assert service._validate_cache_value("string") is False
        assert service._validate_cache_value(None) is False
