"""
Конфигурация приложения.

Централизованное управление настройками через pydantic-settings.
Читается из .env, .env.local (локальные переопределения),
и переменных окружения.
"""
from pathlib import Path


from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- GigaChat ---
    gigachat_credentials: str = ""
    gigachat_model: str = "GigaChat-2"
    scope: str = "GIGACHAT_API_PERS"
    gigachat_verify_ssl: bool = True

    # --- LLM ---
    llm_timeout: int = 30
    llm_retries: int = 3

    # --- Cache ---
    cache_ttl: int = 3600
    cache_max_size: int = 1000
    cache_path: str = "cache/chat_cache.json"

    # --- Fallback ---
    fallback_message: str = "Сервис временно недоступен. Попробуйте позже."

    @property
    def cache_path_object(self) -> Path:
        return Path(self.cache_path)


def get_settings() -> AppSettings:
    """Создаёт экземпляр настроек."""
    return AppSettings()
