"""Тесты конфигурации приложения.

Проверяют реальное поведение AppSettings и get_settings():
- Значения по умолчанию
- Переопределение через пе��еменные окружения
- Типизация и преобразование настроек
- Изоляция через очистку окружения ДО запуска каждого теста
"""
import os
import pytest


@pytest.fixture(autouse=True)
def clean_env():
    """
    Гарантирует, что переменные окружения очищены ДО каждого теста.
    Предотвращает влияние .env или предыдущих тестов на текущий.
    """
    keys_to_clean = [
        "GIGACHAT_CREDENTIALS", "GIGACHAT_MODEL", "SCOPE",
        "LLM_TIMEOUT", "LLM_RETRIES", "CACHE_TTL", "CACHE_MAX_SIZE",
        "FALLBACK_MESSAGE", "CACHE_PATH"
    ]
    for key in keys_to_clean:
        os.environ.pop(key, None)
    yield
    # Дополнительная очистка после теста
    for key in keys_to_clean:
        os.environ.pop(key, None)


class TestAppSettingsDefaults:
    """Проверяют значения по умолчанию в AppSettings."""

    def test_default_model(self):
        """Проверяет, что модель по умолчанию равна GigaChat-2."""
        settings = AppSettings()
        assert settings.gigachat_model == "GigaChat-2"

    def test_default_timeout(self):
        """Проверяет, что timeout по умолчанию равен 30."""
        settings = AppSettings()
        assert settings.llm_timeout == 30

    def test_default_retries(self):
        """Проверяет, что retries по умолчанию равен 3."""
        settings = AppSettings()
        assert settings.llm_retries == 3

    def test_default_scope(self):
        """Проверяет область действия токена по умолчанию."""
        settings = AppSettings()
        assert settings.scope == "GIGACHAT_API_PERS"

    def test_default_cache_ttl(self):
        """Проверяет TTL кэша по умолчанию."""
        settings = AppSettings()
        assert settings.cache_ttl == 3600

    def test_default_cache_max_size(self):
        """Проверяет максимальный размер кэша по умолчанию."""
        settings = AppSettings()
        assert settings.cache_max_size == 1000


class TestAppSettingsOverrides:
    """Проверяют переопределение настроек через переменные окружения."""

    def test_overridden_timeout(self, monkeypatch):
        """Проверяет, что LLM_TIMEOUT из окружения переопределяет default."""
        monkeypatch.setenv("LLM_TIMEOUT", "60")
        settings = AppSettings()
        assert settings.llm_timeout == 60

    def test_overridden_model(self, monkeypatch):
        """Проверяет, что GIGACHAT_MODEL из окружения применяется."""
        monkeypatch.setenv("GIGACHAT_MODEL", "GigaChat")
        settings = AppSettings()
        assert settings.gigachat_model == "GigaChat"

    def test_overridden_retries(self, monkeypatch):
        """Проверяет переопределение количества retry."""
        monkeypatch.setenv("LLM_RETRIES", "5")
        settings = AppSettings()
        assert settings.llm_retries == 5

    def test_credentials_can_be_set(self, monkeypatch):
        """Проверяет установку credentials."""
        monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test_creds_base64")
        settings = AppSettings()
        assert settings.gigachat_credentials == "test_creds_base64"

    def test_get_settings_returns_app_settings(self, monkeypatch):
        """Проверяет, что get_settings() возвращает экземпляр AppSettings."""