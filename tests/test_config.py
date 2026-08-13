"""Тесты конфигурации."""
import os
import pytest
from dotenv import load_dotenv


@pytest.fixture(autouse=True)
def reset_env():
    """Очищает переменные окружения после каждого теста."""
    yield
    for key in ["GIGACHAT_CREDENTIALS", "GIGACHAT_MODEL", "LLM_TIMEOUT", "LLM_RETRIES"]:
        if key in os.environ:
            del os.environ[key]


class TestEnvConfig:
    def test_env_file_exists(self):
        """Проверяет, что .env.example существует."""
        assert os.path.exists(".env.example")

    def test_default_timeout(self):
        """Проверяет значение timeout по умолчанию."""
        timeout = int(os.getenv("LLM_TIMEOUT", "30"))
        assert timeout == 30

    def test_default_retries(self):
        """Проверяет значение retries по умолчанию."""
        retries = int(os.getenv("LLM_RETRIES", "3"))
        assert retries == 3

    def test_default_model(self):
        """Проверяет модель по умолчанию."""
        model = os.getenv("GIGACHAT_MODEL", "GigaChat-2")
        assert model == "GigaChat-2"
