"""
Тесты API endpoints.

Проверяют работу маршрутов FastAPI:
- GET /health — health-check
- POST /chat — отправка сообщения и получение ответа от LLM
"""
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from main import create_app
from services.chat import ChatService, ChatRequest, ChatResponse
from api.router import set_chat_service


# --- Фикстуры ---

@pytest.fixture
def mock_llm_client():
    """
    Создаёт мок-клиент LLM, который возвращает фиксированный ответ.
    Используется для изоляции тестов от реального GigaChat API.
    """
    client = AsyncMock()
    client.generate = AsyncMock(return_value=ChatResponse(reply="Mock answer"))
    return client


@pytest.fixture
def initialized_client(mock_llm_client):
    """
    Создаёт TestClient с полностью инициализированным сервисом (включая LLM-клиент).
    Заменяет стандартный fixture `client`, так как TestClient не запускает startup-события.
    """
    service = ChatService(llm_client=mock_llm_client, fallback_message="Fallback")
    app = create_app()
    set_chat_service(service)
    return TestClient(app)


@pytest.fixture
def client():
    """
    Создаёт TestClient без инициализированного сервиса.
    Используется для тестирования поведения при отсутствии сервиса (503).
    """
    app = create_app()
    return TestClient(app)


# --- Тесты health-check ---

class TestHealthEndpoint:
    """Тесты endpoint GET /health."""

    def test_health_returns_ok(self, client):
        """Проверяет, что health-check возвращает статус 200 и JSON-объект со статусом ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_content_type(self, client):
        """Проверяет, что ответ содержит content-type application/json."""
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]


# --- Тесты чат-endpoint ---

class TestChatEndpoint:
    """Тесты POST /chat."""

    def test_chat_service_not_initialized(self, client):
        """
        Проверяет возврат 503, если ChatService не был инициализирован.
        Это случается, когда startup-событие не сработало (тестовый режим).
        """
        response = client.post("/chat", json={"message": "Test"})
        assert response.status_code == 503

    def test_chat_valid_request(self, initialized_client):
        """Проверяет успешную обработку валидного запроса (статус 200 и наличие поля reply)."""
        response = initialized_client.post("/chat", json={"message": "Привет"})
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data

    def test_chat_empty_message(self, initialized_client):
        """Проверяет возврат 422 при пустом сообщении (pydantic валидация min_length)."""
        response = initialized_client.post("/chat", json={"message": ""})
        assert response.status_code == 422

    def test_chat_missing_message(self, initialized_client):
        """Проверяет возврат 422 при отсутствии поля message в запросе."""
        response = initialized_client.post("/chat", json={})
        assert response.status_code == 422

    def test_chat_message_too_long(self, initialized_client):
        """Проверяет возврат 422 при сообщении длиннее 1000 символов (pydantic валидация max_length)."""
        response = initialized_client.post("/chat", json={"message": "x" * 2000})
        assert response.status_code == 422
