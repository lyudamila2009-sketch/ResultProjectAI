"""
API Router — маршруты для FastAPI приложения.

ChatService передаётся через dependency injection.
В production использует app.state.chat_service (из lifespan).
В тестах может быть переопределён через app.dependency_overrides.
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from services.chat import ChatService
from llm.schemas import ChatRequest, ChatResponse, ChatServiceError
from config.correlation import generate_request_id, set_request_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(request: Request) -> ChatService:
    """
    Получение экземпляра ChatService.

    В production: берётся из app.state.chat_service (инициализирован в lifespan).
    В тестах: может быть переопределён через app.dependency_overrides.
    Если сервис не найден — возвращает 503.
    """
    service = getattr(request.app.state, 'chat_service', None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Сервис не инициализирован. Попробуйте позже.",
        )
    return service


@router.post("", response_model=ChatResponse, description="Отправить сообщение и получить ответ от GigaChat")
async def chat(
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> JSONResponse:
    """
    Принимает валидированное сообщение от пользователя
    и возвращает ответ от GigaChat, кэша или fallback.
    """
    request_id = generate_request_id()
    set_request_id(request_id)

    try:
        logger.info(
            {
                "message": "Вход в /chat endpoint",
                "request_id": request_id,
                "message_length": len(request.message),
            }
        )
        result = await service.chat(request)

        logger.info(
            {
                "message": "Выход из /chat endpoint",
                "request_id": request_id,
                "generation_mode": result.generation_mode,
                "reply_length": len(result.reply),
            }
        )
        return JSONResponse(
            content=result.model_dump(),
            status_code=200,
        )
    except ChatServiceError as exc:
        logger.error(
            {
                "message": "ChatServiceError",
                "request_id": request_id,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(
            {
                "message": "Unexpected error в /chat",
                "request_id": request_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера. Попробуйте позже.",
        )
