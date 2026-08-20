# MyLLMService — GigaChat API Proxy

FastAPI-сервис-прокси для работы с GigaChat API.

## Запуск

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Сервис будет доступен по адресу **http://localhost:8000**

## Конфигурация

Скопируйте `.env.example` в `.env` и заполните значения:

```bash
cp .env.example .env
```

Затем отредактируйте `.env` — обязательно укажите `GIGACHAT_CREDENTIALS`.

```env
GIGACHAT_CREDENTIALS=<base64_encoded client_id:client_secret>
GIGACHAT_MODEL=GigaChat-2
SCOPE=GIGACHAT_API_PERS
LLM_TIMEOUT=30
LLM_RETRIES=3
CACHE_TTL=3600
CACHE_MAX_SIZE=1000
FALLBACK_MESSAGE=Сервис временно недоступен. Попробуйте позже.
```

## Безопасность: 
GIGACHAT_VERIFY_TLS по умолчанию true. Для локальной разработки с self-signed сертификатом 
GigaChat можно временно установить false, но для production всегда оставляйте true и 
устанавливайте CA-сертификат в систему доверия ОС.

| Параметр | Описание | По умолчанию |
|----------|----------|-------------|
| `GIGACHAT_CREDENTIALS` | Base64-encoded `client_id:client_secret` из [developer.sber.ru](https://developer.sber.ru/my/api-keys) | — |
| `GIGACHAT_MODEL` | Модель GigaChat | `GigaChat-2` |
| `GIGACHAT_VERIFY_TLS` | Проверка SSL-сертификатов (не отключайте в production) | `true` |
| `SCOPE` | Область действия токена | `GIGACHAT_API_PERS` |
| `LLM_TIMEOUT` | Таймаут одного запроса к LLM (сек) | `30` |
| `LLM_RETRIES` | Количество попыток при ошибке | `3` |
| `CACHE_TTL` | Время жизни записи в кэше (сек) | `3600` |
| `CACHE_MAX_SIZE` | Максимальное количество записей в кэше | `1000` |
| `FALLBACK_MESSAGE` | Сообщение при недоступности LLM | Сервис временно недоступен. Попробуйте позже. |

## API

### Документация

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

### `GET /health`

Liveness-check: подтверждает, что процесс запущен и отвечает. Не 
проверяет конфигурацию или доступность внешних сервисов. Используется 
оркестраторами (Kubernetes, Docker) для определения жизнеспособности 
контейнера.

**Пример:**
```bash
curl http://localhost:8000/health
```

**Ответ (200):**
```json
{"status": "ok"}
```

### `GET /ready`

Readiness-check: проверяет, что GIGACHAT_CREDENTIALS настроены и
сервис готов обрабатывать запросы. Если credentials пусты — возвращает 503.
Используется для определения готовности сервиса принимать трафик.

**Пример:**
```bash
curl http://localhost:8000/ready
```

**Ответ (200):**
```json
{"status": "ready"}
```

**Ответ (503):**
```json
{"error": "GIGACHAT_CREDENTIALS не настроен"}
```

### `POST /chat`

Отправка сообщения и получение ответа от GigaChat, кэша или fallback.

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
{
  "reply": "Привет! Готов помочь вам. Чем могу быть полезен?",
  "generation_mode": "llm"
}
```

Поле `generation_mode` показывает источник ответа:
- `"llm"` — ответ получен от GigaChat
- `"cache"` — ответ из кэша (memory или disk)
- `"fallback"` — ответ при недоступности LLM

Жизненный цикл приложения
Приложение использует FastAPI lifespan контекстный менеджер для 
управления ресурсами:

startup: создаёт LLMClient и ChatService, сохраняет в app.state
shutdown: очищает app.state.chat_service
В отличие от устаревшего on_event("startup"), lifespan предоставляет 
предсказуемый, изолированный и тестируемый жизненный цикл, 
соответствующий современным стандартам FastAPI.

## Коды ответов

| Код | Значение |
|-----|----------|
| `200` | Успешный ответ (ответ LLM, кэш или fallback) |
| `422` | Ошибка валидации (некорректный ввод) |
| `503` | LLM-клиент не настроен / сервис не готов (проверьте /ready) |
| `500` | Внутренняя ошибка сервера |

## Особенности

- **Кэширование** -- повторные запросы возвращаются из памяти без вызова LLM. Кэш:
  - TTL: записи живут 1 час (`CACHE_TTL`, настраивается)
  - Ограничение: максимум 1000 записей (`CACHE_MAX_SIZE`)
  - Ключ зависит от имени модели и сообщения (case-sensitive)
  - Автосохранение на диск (`cache/chat_cache.json`) с атомарной записью
  - Валидация при восстановлении: повреждённые записи пропускаются
- **Retry** -- при ошибке повторные попытки (настраивается через `LLM_RETRIES`).
- **Timeout** -- запрос к LLM ограничивается по времени (`LLM_TIMEOUT`).
- **Fallback** -- при недоступности LLM возвращается дефолтный ответ с `generation_mode="fallback"`.
- **Correlation ID** -- каждый запрос получает уникальный ID для трассировки в логах.
- **JSON-логи** -- все логи выводятся в структурированном JSON-формате.
- **Lifespan** -- управление жизненным циклом через @asynccontextmanager lifespan вместо устаревшего on_event.

## Логи

Логи пишутся в stdout в структурированном JSON-формате.

Каждая запись содержит:
- `timestamp` — время записи
- `level` — уровень (INFO, WARNING, ERROR)
- `message` — сообщение
- `request_id` — ID запроса для трассировки
- `module` / `funcName` — место в коде

Пример логирования:
```json
{"timestamp": "2024-01-01T00:00:00", "level": "INFO", "message": "Cache miss", "request_id": "abc-123", "message_length": 12}
{"timestamp": "2024-01-01T00:00:01", "level": "INFO", "message": "LLM request succeeded", "request_id": "abc-123", "attempt": 1, "duration_ms": 1500}
{"timestamp": "2024-01-01T00:00:02", "level": "ERROR", "message": "LLM call timed out", "request_id": "abc-123", "timeout_seconds": 30, "attempt": 3}
```

## Тесты

### Запуск

```bash
pip install -r requirements.txt
pytest -v
```

### Структура тестов

| Файл | Охват | Кол-во тестов |
|------|-------|---------------|
| `tests/test_api.py` | API endpoints (`/health`, `/chat`) | 8 |
| `tests/test_chat_models.py` | Pydantic модели (`ChatRequest`, `ChatResponse`) | 8 |
| `tests/test_chat_service.py` | Бизнес-логика, кэш, fallback | 16 |
| `tests/test_llm_post_process.py` | Постобработка ответов LLM | 7 |
| `tests/test_llm_client.py` | Клиент LLM (retry, timeout, конфигурация) | 13 |
| `tests/test_config.py` | Конфигурация (`AppSettings`) | 11 |

**Итого: 63 теста**

### Покрытие

- Валидация входных данных (пустое сообщение, слишком длинное, отсутствует)
- Health-check и readiness-check endpoints
- Обработка неинициализированного сервиса
- Инициализация LLM-клиента и ChatService
- Возврат ответа от LLM и fallback-ответа
- Валидация схем кэша
- Корректность ключей кэша (детерминированность, case-sensitive, с учётом модели)
- Проверка TTL кэша
- Однократный вызов LLM при повторных запросах (кэширование)
- Восстановление кэша из файла после перезапуска
- Обработка повреждённого файла кэша
- Изоляция тестов через cleanup dependency_overrides и tmp_path
- Значения по умолчанию AppSettings
- Переопределение настроек через переменные окружения
- Постобработка ответов SDK (post_process)
- Retry при ошибках LLM
- Исчерпание retry и финальное исключение
- Timeout обработка
- Загрузка конфигурации при отсутствии AppSettings