import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from llm.client import LLMClient
from services.chat import ChatService
from api.router import router as chat_router, set_chat_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_chat_service: ChatService | None = None


def _init_service() -> ChatService:
    """Инициализируем LLMClient и ChatService."""
    global _chat_service
    logger.info("Инициализация LLM-клиента...")
    llm_client = LLMClient()
    fallback = "Сервис временно недоступен. Попробуйте позже."
    logger.info("Инициализация ChatService...")
    _chat_service = ChatService(llm_client=llm_client, fallback_message=fallback)
    set_chat_service(_chat_service)
    return _chat_service


def create_app() -> FastAPI:
    """Создаём и настраиваем FastAPI-приложение."""
    app = FastAPI(title="MyLLMService API")

    @app.on_event("startup")
    async def startup():
        _init_service()

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("Приложение остановлено.")

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    app.include_router(chat_router)
    return app


# Запускаем приложение
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
