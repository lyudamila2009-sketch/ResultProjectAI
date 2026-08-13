import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from services.chat import ChatService, ChatRequest, ChatResponse, ChatServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

_chat_service: ChatService | None = None


def set_chat_service(service: ChatService) -> None:
    """Передаёт экземпляр ChatService в роутер."""
    global _chat_service
    _chat_service = service


def get_chat_service() -> ChatService:
    """Зависимость для получения экземпляра ChatService."""
    if _chat_service is None:
        raise HTTPException(
            status_code=503,
            detail="Сервис не инициализирован. Попробуйте позже.",
        )
    return _chat_service


@router.post("", response_model=ChatResponse, description="Отправить сообщение и получить ответ от GigaChat")
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """
    Принимает валидированное сообщение от пользователя
    и возвращает ответ от GigaChat.
    """
    try:
        return await service.chat(request)
    except ChatServiceError as exc:
        logger.error(f"ChatService error: {exc}")
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера. Попробуйте позже.",
        )
