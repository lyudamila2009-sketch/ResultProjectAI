"""
Тесты LLMClient — клиент для взаимодействия с GigaChat API.

Проверяют:
- Загрузку конфигурации из AppSettings
- Постобработку ответов (post_process)
- Retry логику при ошибках
- Timeout обработку
- Типизацию настроек
"""
import asyncio
import pytest
from unittest.mock import MagicMock, patch
from config.settings import AppSettings
from llm.client import LLMClient


@pytest.fixture(autouse=True)
def _clean_env_for_llm_tests():
    """Очищает переменные окружения ДО каждого теста в test_llm_client.py."""
    import os
    keys_to_clean = [
        "GIGACHAT_CREDENTIALS", "GIGACHAT_MODEL", "SCOPE",
        "LLM_TIMEOUT", "LLM_RETRIES", "CACHE_TTL", "CACHE_MAX_SIZE",
        "FALLBACK_MESSAGE", "CACHE_PATH"
    ]
    for key in keys_to_clean:
        os.environ.pop(key, None)
    yield
    for key in keys_to_clean:
        os.environ.pop(key, None)


class TestLLMClientConfig:
    """Тесты загрузки конфигурации LLMClient."""

    def test_load_config_all_fields(self):
        """Проверяет, что _load_config копирует все поля из AppSettings."""
        settings = AppSettings(
            gigachat_credentials="test_creds",
            scope="TEST_SCOPE",
            gigachat_model="GigaChat-2",
            llm_timeout=60,
            llm_retries=5,
        )
        client = LLMClient(settings=settings)
        assert client._config.credentials == "test_creds"
        assert client._config.scope == "TEST_SCOPE"
        assert client._config.model == "GigaChat-2"
        assert client._config.timeout == 60
        assert client._config.retries == 5

    def test_load_config_defaults(self):
        """Проверяет, что _load_config применяет дефолтные значения."""
        settings = AppSettings()
        client = LLMClient(settings=settings)
        # credentials могут быть из .env — проверяем другие поля
        assert client._config.scope == "GIGACHAT_API_PERS"
        assert client._config.model == "GigaChat-2"
        assert client._config.timeout == 30
        assert client._config.retries == 3
        assert isinstance(client._config.timeout, int)
        assert isinstance(client._config.retries, int)

    def test_load_config_type_conversion(self):
        """Проверяет, что timeout и retries сохраняются как int, а не str."""
        settings = AppSettings()
        client = LLMClient(settings=settings)
        assert isinstance(client._config.timeout, int)
        assert isinstance(client._config.retries, int)
        assert client._config.timeout == 30
        assert client._config.retries == 3

    def test_no_settings_creates_appsettings(self):
        """Проверяет, что без параметров LLMClient создаёт AppSettings()."""
        with patch("llm.client.AppSettings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.gigachat_credentials = ""
            mock_settings.scope = "GIGACHAT_API_PERS"
            mock_settings.gigachat_model = "GigaChat-2"
            mock_settings.llm_timeout = 30
            mock_settings.llm_retries = 3
            mock_settings_cls.return_value = mock_settings
            client = LLMClient()
            assert client._config is not None
            mock_settings_cls.assert_called_once()


class TestPostProcess:
    """Тесты _post_process для парсинга ответа SDK."""

    def test_post_process_valid_response(self):
        """Валидный ответ с choices и content возвращается."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "  Hello  World  "
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        client = LLMClient()
        result = client._post_process(mock_response)
        assert result == "Hello World"

    def test_post_process_empty_choices(self):
        """Пустые choices возвращают пустую строку."""
        mock_response = MagicMock()
        mock_response.choices = []

        client = LLMClient()
        result = client._post_process(mock_response)
        assert result == ""

    def test_post_process_no_choices_attribute(self):
        """Ответ без атрибута choices возвращает пустую строку."""
        mock_response = MagicMock(spec=[])

        client = LLMClient()
        result = client._post_process(mock_response)
        assert result == ""

    def test_post_process_none_content(self):
        """content=None возвращает пустую строку."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response.choices = [mock_choice]

        client = LLMClient()
        result = client._post_process(mock_response)
        assert result == ""

    def test_post_process_whitespace_only(self):
        """Только пробелы/переносы строк возвращают пустую строку."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "\n  \t  "
        mock_response.choices = [mock_choice]

        client = LLMClient()
        result = client._post_process(mock_response)
        assert result == ""


class TestGenerateRetry:
    """Тесты retry и timeout логики generate()."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Проверяет, что generate повторяет вызов при ошибке LLM."""
        with (
            patch("llm.client.asyncio.wait_for") as mock_wait_for,
            patch("llm.client.asyncio.get_running_loop") as mock_loop,
            patch("llm.client.logger") as mock_logger,
        ):
            mock_executor = MagicMock()
            mock_loop.return_value.run_in_executor = mock_executor

            # Первый вызов — ошибка, второй — успех
            mock_executor.side_effect = [
                ConnectionError("Connection refused"),
                MagicMock(choices=[MagicMock(message=MagicMock(content="OK"))]),
            ]

            settings = AppSettings(llm_retries=2, llm_timeout=5)
            client = LLMClient(settings=settings)

            with patch.object(client, "_post_process", return_value="OK"):
                result = await client.generate(system="sys", user="usr")

            assert result.reply == "OK"
            assert mock_executor.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_all_retries(self):
        """Проверяет, что generate бросает ошибку после исчерпания retries."""
        with (
            patch("llm.client.asyncio.wait_for") as mock_wait_for,
            patch("llm.client.asyncio.get_running_loop") as mock_loop,
            patch("llm.client.logger") as mock_logger,
        ):
            mock_executor = MagicMock()
            mock_loop.return_value.run_in_executor = mock_executor

            # Все попытки падают
            mock_executor.side_effect = ConnectionError("Network error")

            settings = AppSettings(llm_retries=3, llm_timeout=5)
            client = LLMClient(settings=settings)

            with pytest.raises(ConnectionError):
                await client.generate(system="sys", user="usr")

            assert mock_executor.call_count == 3

    @pytest.mark.asyncio
    async def test_single_call_when_retries_one(self):
        """Проверяет, что при retries=1 нет повторных попыток."""
        with (
            patch("llm.client.asyncio.wait_for"),
            patch("llm.client.asyncio.get_running_loop") as mock_loop,
            patch("llm.client.logger"),
        ):
            mock_executor = MagicMock()
            mock_loop.return_value.run_in_executor = mock_executor
            mock_executor.side_effect = ConnectionError("Network error")

            settings = AppSettings(llm_retries=1, llm_timeout=5)
            client = LLMClient(settings=settings)

            with pytest.raises(ConnectionError):
                await client.generate(system="sys", user="usr")

            assert mock_executor.call_count == 1

    @pytest.mark.asyncio
    async def test_timeout_raises_after_retries(self):
        """Проверяет, что TimeoutError бросается после всех retry попыток."""
        with (
            patch("llm.client.asyncio.wait_for") as mock_wait_for,
            patch("llm.client.asyncio.get_running_loop") as mock_loop,
            patch("llm.client.logger"),
        ):
            mock_loop.return_value.run_in_executor = MagicMock()
            mock_wait_for.side_effect = asyncio.TimeoutError("Timeout")

            settings = AppSettings(llm_retries=2, llm_timeout=1)
            client = LLMClient(settings=settings)

            with pytest.raises(asyncio.TimeoutError):
                await client.generate(system="sys", user="usr")

            assert mock_wait_for.call_count == 2
