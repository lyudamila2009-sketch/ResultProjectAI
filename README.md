# MyLLMService — GigaChat API Proxy

FastAPI-сервис-прокси для работы с GigaChat API.

## Запуск

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Сервис будет доступен по адресу **http://localhost:8000**

## Конфигурация

Создайте файл `.env` в корне проекта:

```env
GIGACHAT_CREDENTIALS=<base64_encoded client_id:client_secret>
GIGACHAT_MODEL=GigaChat-2
LLM_TIMEOUT=30
LLM_RETRIES=3
```

| Параметр | Описание | По умолчанию |
|----------|----------|-------------|
| `GIGACHAT_CREDENTIALS` | Base64-encoded `client_id:client_secret` из [developer.sber.ru](https://developer.sber.ru/my/api-keys) | — |
| `GIGACHAT_MODEL` | Модель GigaChat | `GigaChat-2` |
| `LLM_TIMEOUT` | Таймаут одного запроса к LLM (сек) | `30` |
| `LLM_RETRIES` | Количество попыток при ошибке | `3` |

## API

### Документация

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

### `GET /health`

Проверка состояния сервиса.

**Пример:**
```bash
curl http://localhost:8000/health
```

**Ответ (200):**
```json
{"status": "ok"}
```

### `POST /chat`

Отправка сообщения и получение ответа от GigaChat.

**Тело запроса:**

| Поле | Тип | Описание |
|------|-----|----------|
| `message` | string | Сообщение пользователя (1-1000 символов) |

**Пример:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Как дела?"}'
```

**Ответ (200):**
```json
{"reply": "Привет! Готов помочь вам. Чем могу быть полезен?"}
```

## Коды ответов

| Код | Значение |
|-----|----------|
| `200` | Успешный ответ от LLM или из кэша |
| `422` | Ошибка валидации (некорректный ввод) |
| `503` | LLM-клиент не настроен / сервис не инициализирован |
| `500` | Внутренняя ошибка сервера |

## Особенности

- **Кэширование** -- повторные запросы возвращаются из памяти без вызова LLM. Кэш сохраняется на диск (`cache/chat_cache.json`) и восстанавливается при перезапуске.
- **Retry** -- при ошибке повторные попытки (настраивается через `LLM_RETRIES`).
- **Timeout** -- запрос к LLM ограничивается по времени (`LLM_TIMEOUT`).
- **Fallback** -- при недоступности LLM возвращается дефолтный ответ без падения сервиса.

## Логи

Логи пишутся в stdout.

## Тесты

### Запуск

```bash
pip install -r requirements.txt
pytest -v
```

### Структура тестов

| Файл | Охват | Кол-во тестов |
|------|-------|---------------|
| `tests/test_api.py` | API endpoints (`/health`, `/chat`) | 7 |
| `tests/test_chat_models.py` | Pydantic модели (`ChatRequest`, `ChatResponse`) | 5 |
| `tests/test_chat_service.py` | Бизнес-логика, кэш, fallback | 7 |

**Итого: 19 тестов**

### Покрытие

- Валидация входных данных (пустое сообщение, слишком длинное, отсутствует)
- Health-check endpoint
- Обработка неинициализированного сервиса
- Инициализация LLM-клиента и ChatService
- Возврат ответа от LLM и fallback-ответа
- Детерминированность и case-insensitive ключей кэша