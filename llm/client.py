import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

from gigachat import GigaChat
from gigachat.models.chat import Messages
from dotenv import load_dotenv

from services.chat import ChatResponse

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Конфигурация LLM-клиента из .env."""
    credentials: str
    scope: str
    model: str
    retries: int
    timeout: int


class LLMClient:
    """
    Клиент для взаимодействия с GigaChat API.
    Конфигурация загружается из .env (GIGACHAT_CREDENTIALS, SCOPE, GIGACHAT_MODEL).
    GigaChat SDK использует sync-вызовы, поэтому оборачиваем их через run_in_executor.
    """

    def __init__(self):
        self._config = self._load_config()
        self._client: Optional[GigaChat] = None

    def _load_config(self) -> LLMConfig:
        """Загрузить конфигурацию из переменных окружения."""
        return LLMConfig(
            credentials=os.getenv("GIGACHAT_CREDENTIALS", ""),
            scope=os.getenv("SCOPE", "GIGACHAT_API_PERS"),
            model=os.getenv("GIGACHAT_MODEL", "GigaChat-2"),
            retries=int(os.getenv("LLM_RETRIES", "3")),
            timeout=int(os.getenv("LLM_TIMEOUT", "30")),
        )

    def _create_client(self) -> GigaChat:
        """Создать экземпляр GigaChat клиента (синхронно)."""
        return GigaChat(
            credentials=self._config.credentials,
            scope=self._config.scope,
            verify_ssl_certs=False,
        )

    async def generate(self, system: str, user: str) -> ChatResponse:
        """
        Отправить сообщения к GigaChat и вернуть ответ.

        Args:
            system: системный промпт, задаёт поведение LLM.
            user: пользовательское сообщение.

        Raises:
            Exception: если все попытки с retry исчерпаны или таймаут.

        GigaChat SDK sync-вызовы оборачиваются в run_in_executor,
        чтобы не блокировать event loop.
        """
        for attempt in range(self._config.retries):
            try:
                def _chat():
                    client = self._create_client()
                    system_msg = Messages(role="system", content=system)
                    user_msg = Messages(role="user", content=user)
                    payload = {
                        "model": self._config.model,
                        "messages": [system_msg, user_msg],
                    }
                    logger.debug(f"Payload: {payload}")
                    return client.chat(payload)

                loop = asyncio.get_running_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, _chat),
                    timeout=self._config.timeout,
                )
                reply = response.choices[0].message.content
                return ChatResponse(reply=reply)
            except asyncio.TimeoutError:
                logger.error(
                    f"LLM call timed out ({self._config.timeout}s), "
                    f"attempt {attempt + 1}/{self._config.retries}",
                )
                if attempt == self._config.retries - 1:
                    raise
            except Exception as exc:
                logger.error(
                    f"LLM call failed (attempt {attempt + 1}/{self._config.retries}): "
                    f"{type(exc).__name__}: {exc}",
                )
                if attempt == self._config.retries - 1:
                    raise

        return ChatResponse(reply=user)
