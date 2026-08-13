import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ChatServiceError(Exception):
    """Ошибка сервиса обработки чата (например, недоступность LLM)."""
    pass


class ChatRequest(BaseModel):
    """Валидированный запрос от /api/chat."""
    message: str = Field(..., min_length=1, max_length=1000, description="Сообщение пользователя")


class ChatResponse(BaseModel):
    """Ответ от LLM-сервиса."""
    reply: str


SYSTEM_PROMPT = (
    "Ты — полезный ассистент. Отвечай кратко и по существу. "
    "Если не уверен в ответе, честно скажи об этом."
)


_CACHE_PATH = Path(__file__).parent.parent / "cache" / "chat_cache.json"


class ChatService:
    """
    Сервис для обработки чат-запросов.
    Принимает валидированный запрос и формирует вызов к LLM-клиенту.
    Использует кэш для повторных запросов, fallback-ответы при недоступности LLM.
    """

    def __init__(self, llm_client=None, fallback_message: Optional[str] = None):
        """
        Инициализация сервиса.

        Args:
            llm_client: клиент для взаимодействия с GigaChat.
            fallback_message: ответ при недоступности LLM.
        """
        self._llm_client = llm_client
        self._fallback_message = fallback_message or "Сервис временно недоступен. Попробуйте позже."
        self._cache_path = _CACHE_PATH
        self._ensure_cache_dir()
        self._cache: dict[str, dict] = self._load_cache()
        self._cache_responses: dict[str, ChatResponse] = {}

    def _ensure_cache_dir(self):
        """Создать директорию для кэша, если не существует."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> dict[str, dict]:
        """Загрузить кэш с диска."""
        if self._cache_path.exists():
            try:
                data = json.loads(self._cache_path.read_text(encoding="utf-8"))
                logger.info(f"Кэш загружен: {len(data)} записей")
                return data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(f"Не удалось загрузить кэш, создаю новый: {exc}")
        return {}

    def _save_cache(self):
        """Сохранить кэш на диск."""
        try:
            self._cache_path.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning(f"Не удалось сохранить кэш: {exc}")

    def _cache_key(self, message: str) -> str:
        """Создать ключ кэша из сообщения пользователя."""
        return hashlib.sha256(message.strip().lower().encode()).hexdigest()

    def _get_from_cache(self, message: str) -> Optional[ChatResponse]:
        """Проверить кэш по сообщению пользователя."""
        key = self._cache_key(message)
        cached = self._cache_responses.get(key)
        if cached:
            logger.info(f"Cache hit for message: {message[:50]}...")
        else:
            # Попытка восстановить из дискового кэша
            if key in self._cache:
                cached = ChatResponse(**self._cache[key])
                self._cache_responses[key] = cached
                logger.info(f"Cache hit (from disk) for message: {message[:50]}...")
        return cached

    def _set_cache(self, message: str, response: ChatResponse):
        """Сохранить ответ в кэш (память + диск)."""
        key = self._cache_key(message)
        self._cache[key] = response.model_dump()
        self._cache_responses[key] = response
        self._save_cache()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Обработать запрос и вернуть ответ от LLM или кэша.
        Передаёт LLM-клиенту системный промпт + пользовательское сообщение.
        При ошибке LLM возвращает fallback-ответ.

        Args:
            request: валидированный запрос с полем message.

        Returns:
            ChatResponse с ответом от LLM, кэша или fallback.
        """
        # 1. Проверяем кэш
        cached = self._get_from_cache(request.message)
        if cached:
            return cached

        # 2. Если кэша нет — запрашиваем у LLM
        if self._llm_client is None or not hasattr(self._llm_client, 'generate'):
            raise ChatServiceError("LLM-клиент не настроен")

        try:
            response = await self._llm_client.generate(
                system=SYSTEM_PROMPT,
                user=request.message,
            )
            # 3. Сохраняем в кэш
            self._set_cache(request.message, response)
            return response
        except Exception as exc:
            error_msg = f"Ошибка LLM-запроса: {exc}"
            logger.error(error_msg)
            # 4. Fallback — возвращаем осмысленный ответ, не бросаем исключение
            return ChatResponse(reply=self._fallback_message)
