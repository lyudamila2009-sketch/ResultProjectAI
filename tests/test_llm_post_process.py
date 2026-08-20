import pytest
from llm.client import LLMClient
from unittest.mock import MagicMock


class TestPostProcess:
    """Тесты слоя постобработки ответов LLM."""

    def _create_mock_response(self, choices_data):
        """Вспомогательная функция для создания мок-ответа."""
        response = MagicMock()
        response.choices = choices_data
        return response

    def _create_choice(self, content=None):
        """Вспомогательная функция для создания мок-выбора."""
        choice = MagicMock()
        message = MagicMock()
        message.content = content
        choice.message = message
        return choice

    def test_post_process_valid_response(self):
        """Нормальный валидный ответ."""
        llm = LLMClient()
        choice = self._create_choice(content="Hello world")
        response = self._create_mock_response([choice])
        result = llm._post_process(response)
        assert result == "Hello world"

    def test_post_process_strips_whitespace(self):
        """Ответ должен быть очищен от пробелов."""
        llm = LLMClient()
        choice = self._create_choice(content="  Hello  ")
        response = self._create_mock_response([choice])
        result = llm._post_process(response)
        assert result == "Hello"

    def test_post_process_empty_choices(self):
        """Пустой список choices должен вернуть пустую строку."""
        llm = LLMClient()
        response = self._create_mock_response([])
        result = llm._post_process(response)
        assert result == ""

    def test_post_process_none_content(self):
        """None content должен вернуть пустую строку."""
        llm = LLMClient()
        choice = self._create_choice(content=None)
        response = self._create_mock_response([choice])
        result = llm._post_process(response)
        assert result == ""

    def test_post_process_whitespace_only(self):
        """Ответ из пробелов должен вернуть пустую строку."""
        llm = LLMClient()
        choice = self._create_choice(content="   \n\n  ")
        response = self._create_mock_response([choice])
        result = llm._post_process(response)
        assert result == ""

    def test_post_process_normalize_lines(self):
        """Множественные переносы строк должны быть нормализованы."""
        llm = LLMClient()
        choice = self._create_choice(content="Hello\n\n\nWorld")
        response = self._create_mock_response([choice])
        result = llm._post_process(response)
        assert result == "Hello World"

    def test_post_process_no_choices_attribute(self):
        """Отсутствие choices атрибута."""
        llm = LLMClient()
        response = MagicMock()
        response.choices = None
        result = llm._post_process(response)
        assert result == ""
