import asyncio
import fcntl
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from config.correlation import get_request_id
from llm.schemas import ChatRequest, ChatResponse, ChatServiceError, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).parent.parent / "cache" / "chat_cache.json"
_DEFAULT_CACHE_TTL = 3600  # 1 час
_DEFAULT_CACHE_MAX_SIZE = 1000


class ChatService:
    """
    Сервис для обработки чат-запросов.
    Принимает валидированный запрос и формирует вызов к LLM-клиенту.
    Использует кэш с TTL и ограничением размера, fallback-ответы при недоступности LLM.
    """

    def __init__(
        self,
        llm_client=None,
        fallback_message: Optional[str] = None,
        cache_ttl: float = _DEFAULT_CACHE_TTL,
        cache_max_size: int = _DEFAULT_CACHE_MAX_SIZE,
        cache_path: Path = _CACHE_PATH,
        model_name: str = "",
    ):
        """
        Инициализация сервиса.

        Args:
            llm_client: клиент для взаимодействия с GigaChat.
            fallback_message: ответ при недоступности LLM.
            cache_ttl: время жизни записи кэша в секундах (0 — отключён).
            cache_max_size: максимальное количество записей в кэше.
            cache_path: путь к файлу дисквого кэша.
            model_name: имя модели для формирования ключа кэша.
        """
        self._llm_client = llm_client
        self._fallback_message = fallback_message or "Сервис временно недоступен. Попробуйте позже."
        self._cache_path = cache_path
        self._cache_ttl = cache_ttl
        self._cache_max_size = cache_max_size
        self._model_name = model_name
        self._ensure_cache_dir()
        self._cache: dict[str, dict[str, Any]] = self._load_cache()
        self._cache_responses: dict[str, ChatResponse] = {}

    def _ensure_cache_dir(self):
        """Создать директорию для кэша, если не существует."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_cache_value(value: Any) -> bool:
        """
        Проверить, что значение кэш-записи соответствует ожидаемой схеме.

        Валидируется:
        - value — dict с полями 'reply' (str) и 'created_at' (float).

        Args:
            value: загруженное из JSON значение.

        Returns:
            True, если схема валидна.
        """
        if not isinstance(value, dict):
            return False
        if "reply" not in value or "created_at" not in value:
            return False
        if not isinstance(value["reply"], str):
            return False
        if not isinstance(value["created_at"], (int, float)):
            return False
        return True

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        """Загрузить кэш с диска."""
        request_id = get_request_id()
        if self._cache_path.exists():
            try:
                data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    {
                        "message": "Не удалось загрузить кэш, создаю новый",
                        "request_id": request_id,
                        "error": str(exc),
                    }
                )
                return {}

            if not isinstance(data, dict):
                logger.warning(
                    {
                        "message": "Кэш имеет неверный формат (ожидался dict), создаю новый",
                        "request_id": request_id,
                    }
                )
                return {}

            # Валидация каждой записи и фильтрация невалидных
            cleaned: dict[str, dict[str, Any]] = {}
            skipped = 0
            for key, value in data.items():
                if self._validate_cache_value(value):
                    cleaned[key] = value
                else:
                    skipped += 1
                    logger.warning(
                        {
                            "message": "Пропущена повреждённая кэш-запись",
                            "request_id": request_id,
                            "cache_key": key[:12],
                        }
                    )

            logger.info(
                {
                    "message": "Кэш загружен",
                    "request_id": request_id,
                    "loaded": len(cleaned),
                    "skipped": skipped,
                }
            )
            return cleaned
        return {}

    async def _save_cache(self):
        """
        Сохранить кэш на диск асинхронно (атомарная запись с файловой блокировкой).

        Использует fcntl.flock для защиты от конкурентного доступа:
        - EXclusive locking для записи
        - Блокировка снимается автоматически при выходе из контекста
        """
        def _write():
            content = json.dumps(self._cache, ensure_ascii=False, indent=2)
            tmp_path = self._cache_path.with_suffix(".tmp")
            # Сериализация в временный файл
            tmp_path.write_text(content, encoding="utf-8")

            # Атомарная замена + эксклюзивная блокировка
            with open(self._cache_path, "a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    os.replace(tmp_path, self._cache_path)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        await asyncio.to_thread(_write)

    def _cache_key(self, message: str) -> str:
        """
        Создать ключ кэша из сообщения и имени модели.
        Ключ чувствителен к регистру (case-sensitive).
        """
        raw = f"{self._model_name}:{message}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _evict_expired(self) -> int:
        """Удалить истёкшие записи из кэша. Возвращает количество удалённых."""
        if not self._cache_ttl or self._cache_ttl <= 0:
            return 0
        now = time.time()
        expired = [
            key for key, value in self._cache.items()
            if (now - value["created_at"]) > self._cache_ttl
        ]
        for key in expired:
            del self._cache[key]
        return len(expired)

    def _evict_old_if_full(self):
        """
        Если кэш достиг лимита, удалить самые старые записи,
        пока размер не станет допустимым.
        """
        if len(self._cache) <= self._cache_max_size:
            return

        # Сортируем по created_at и удаляем самые старые
        sorted_keys = sorted(
            self._cache,
            key=lambda k: self._cache[k]["created_at"],
        )
        to_remove = len(sorted_keys) - self._cache_max_size
        for key in sorted_keys[:to_remove]:
            del self._cache[key]
            logger.info(
                {
                    "message": "Evicted old cache entry (cache full)",
                    "cache_key": key[:12],
                }
            )

    def _get_from_cache(self, message: str) -> Optional[ChatResponse]:
        """Проверить кэш по сообщению пользователя."""
        request_id = get_request_id()
        key = self._cache_key(message)

        if self._cache_ttl and self._cache_ttl > 0:
            expired_count = self._evict_expired()
            if expired_count > 0:
                logger.info(
                    {
                        "message": "Cache entries evicted due to TTL",
                        "request_id": request_id,
                        "evicted": expired_count,
                        "cache_size": len(self._cache),
                    }
                )

        cached = self._cache_responses.get(key)
        if cached:
            logger.info(
                {
                    "message": "Cache hit (memory)",
                    "request_id": request_id,
                    "message_length": len(message),
                }
            )
            return cached

        # Попытка восстановить из дискового кэша
        if key in self._cache:
            value = self._cache[key]
            if self._validate_cache_value(value):
                cached = ChatResponse(**value)
                self._cache_responses[key] = cached
                logger.info(
                    {
                        "message": "Cache hit (disk)",
                        "request_id": request_id,
                        "message_length": len(message),
                    }
                )
                return cached
            else:
                logger.warning(
                    {
                        "message": "Повреждённая запись в дисковом кэше, удаляем",
                        "request_id": request_id,
                        "cache_key": key[:12],
                    }
                )
                del self._cache[key]

        # Cache miss
        logger.info(
            {
                "message": "Cache miss",
                "request_id": request_id,
                "message_length": len(message),
            }
        )
        return None

    async def _set_cache(self, message: str, response: ChatResponse):
        """Сохранить ответ в кэш (память + диск)."""
        request_id = get_request_id()
        key = self._cache_key(message)
        self._cache[key] = response.model_dump()
        self._cache[key]["created_at"] = time.time()
        self._cache_responses[key] = response

        # Ограничение размера кэша
        self._evict_old_if_full()

        # Асинхронная дисковая запись
        await self._save_cache()

        logger.info(
            {
                "message": "Cache save",
                "request_id": request_id,
                "message_length": len(message),
                "cache_size": len(self._cache),
            }
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Обработать запрос и вернуть ответ от LLM, кэша или fallback.

        Args:
            request: валидированный запрос с полем message.

        Returns:
            ChatResponse с ответом от LLM, кэша или fallback.

        Raises:
            ChatServiceError: если LLM-клиент не настроен.
        """
        request_id = get_request_id()
        message = request.message

        # 1. Проверяем кэш
        cached = self._get_from_cache(message)
        if cached:
            cached.generation_mode = "cache"
            return cached

        # 2. Если кэжа нет — проверяем наличие LLM-клиента
        if self._llm_client is None or not hasattr(self._llm_client, 'generate'):
            raise ChatServiceError("LLM-клиент не настроен")

        try:
            response = await self._llm_client.generate(
                system=SYSTEM_PROMPT,
                user=message,
            )
            response.generation_mode = "llm"
            # 3. Сохраняем в кэш
            await self._set_cache(message, response)
            return response
        except Exception as exc:
            logger.error(
                {
                    "message": "Ошибка LLM-запроса, используем fallback",
                    "request_id": request_id,
                    "error": str(exc),
                }
            )
            # 4. Fallback — возвращаем ответ с явным признаком деградации
            return ChatResponse(
                reply=self._fallback_message,
                generation_mode="fallback",
            )
