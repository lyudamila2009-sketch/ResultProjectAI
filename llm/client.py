"""
Клиент для взаимодействия с GigaChat API.

Конфигурация читается из AppSettings (config/settings.py).
Использует структурированное JSON-логирование.
"""
import asyncio
import logging
import sys
from dataclasses import dataclass
from typing import Optional

from gigachat import GigaChat
from gigachat.models.chat import Messages

from config.settings import AppSettings
from config.correlation import get_request_id
from llm.schemas import ChatResponse

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Конфигурация LLM-клиента."""
    credentials: str
    scope: str
    model: str
    retries: int
    timeout: int
    verify_ssl: bool = True


class LLMClient:
    """
    Клиент для взаимодействия с GigaChat API.
    GigaChat SDK использует sync-вызовы, поэтому оборачиваем их через run_in_executor.
    """

    def __init__(self, settings: Optional[AppSettings] = None):
        """
        Инициализация LLM-клиента.

        Args:
            settings: экземпляр настроек. Если не передан -- создаётся новый.
        """
        self._settings = settings or AppSettings()
        self._config = self._load_config()

    def _load_config(self) -> LLMConfig:
        """Загрузить конфигурацию из AppSettings."""
        return LLMConfig(
            credentials=self._settings.gigachat_credentials,
            scope=self._settings.scope,
            model=self._settings.gigachat_model,
            retries=self._settings.llm_retries,
            timeout=self._settings.llm_timeout,
            verify_ssl=self._settings.gigachat_verify_ssl,
        )

    def _create_client(self) -> GigaChat:
        """Создать экземпляр GigaChat клиента (синхронно)."""
        return GigaChat(
            credentials=self._config.credentials,
            scope=self._config.scope,
            verify_ssl_certs=self._config.verify_ssl,
        )

    def _post_process(self, response) -> str:
        """Постобработка ответа от LLM."""
        if not hasattr(response, "choices") or not response.choices:
            return ""
        choice = response.choices[0]
        if not hasattr(choice, "message"):
            return ""
        message = choice.message
        if not hasattr(message, "content") or message.content is None:
            return ""
        cleaned = message.content.strip()
        if not cleaned:
            return ""
        return " ".join(cleaned.split())

    async def generate(self, system: str, user: str) -> ChatResponse:
        """
        Отправить сообщения к GigaChat и вернуть ответ.
        """
        request_id = get_request_id()

        for attempt in range(self._config.retries):
            try:
                def _chat():
                    client = self._create_client()
                    system_msg = Messages(role="system", content=system)
                    user_msg = Messages(role="user", content=user)
                    return client.chat({
                        "model": self._config.model,
                        "messages": [system_msg, user_msg],
                    })

                loop = asyncio.get_running_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, _chat),
                    timeout=self._config.timeout,
                )
                raw_reply = self._post_process(response)
                if not raw_reply:
                    raise ValueError("Empty response from LLM")
                return ChatResponse(reply=raw_reply)

            except asyncio.TimeoutError:
                if attempt == self._config.retries - 1:
                    logger.exception(
                        {
                            "message": "LLM request timed out after all retries",
                            "request_id": request_id,
                            "attempt": attempt + 1,
                            "timeout": self._config.timeout,
                        }
                    )
                    raise
            except Exception:
                if attempt == self._config.retries - 1:
                    exc_type = type(sys.exc_info()[1]).__name__
                    logger.exception(
                        {
                            "message": "LLM request failed after all retries",
                            "request_id": request_id,
                            "attempt": attempt + 1,
                            "error_type": exc_type,
                        }
                    )
                    raise

        return ChatResponse(reply=user)
