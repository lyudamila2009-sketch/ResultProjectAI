"""
FastAPI-приложение для работы с GigaChat API.

Использует FastAPI lifespan для управления жизненным циклом приложения.
Чёткое разделение liveness (/health) и readiness (/ready).
Глобальное состояние минимизировано - ресурсы создаются в lifespan.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from config.settings import AppSettings, get_settings
from config.logging_config import setup_logging
from config.correlation import setup_request_id_logging
from llm.client import LLMClient
from services.chat import ChatService
from api.router import router as chat_router, get_chat_service

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Создаём и настраиваем FastAPI-приложение."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        Жизненный цикл приложения.
        startup: создаёт LLMClient и ChatService.
        shutdown: очищает состояние.
        """
        logger.info("Инициализация LLM-клиента...")

        settings = get_settings()

        if not settings.gigachat_credentials:
            logger.warning(
                "GIGACHAT_CREDENTIALS пустые - сервис будет работать в fallback-режиме"
            )

        llm_client = LLMClient(settings=settings)
        chat_service = ChatService(
            llm_client=llm_client,
            fallback_message=settings.fallback_message,
            cache_ttl=settings.cache_ttl,
            cache_max_size=settings.cache_max_size,
            cache_path=settings.cache_path_object,
            model_name=settings.gigachat_model,
        )

        app.state.chat_service = chat_service
        logger.info("ChatService инициализирован")

        yield

        logger.info("Остановка приложения...")
        app.state.chat_service = None

    app = FastAPI(
        title="MyLLMService API",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["health"])
    async def health():
        """Liveness-check: подтверждает, что процесс запущен и отвечает."""
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def ready():
        """
        Readiness-check: проверяет, что credentials настроены.
        Возвращает 503, если сервис не готов к работе.
        """
        settings = get_settings()
        if not settings.gigachat_credentials:
            return Response(
                status_code=503,
                content='{"error": "GIGACHAT_CREDENTIALS не настроен"}',
                media_type="application/json",
            )
        return {"status": "ready"}

    app.include_router(chat_router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)