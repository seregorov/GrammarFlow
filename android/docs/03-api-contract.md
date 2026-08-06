# API-контракт (общий с десктопом)

Источник правды: [`../../GrammarFlow/api_client.py`](../../GrammarFlow/api_client.py), [`../../GrammarFlow/models.py`](../../GrammarFlow/models.py), [`../../GrammarFlow/config.py`](../../GrammarFlow/config.py).

## HTTP

```
POST https://ai.api.cloud.yandex.net/v1/chat/completions
```

### Headers

```http
Authorization: Api-Key {YANDEX_API_KEY}
x-folder-id: {YANDEX_FOLDER_ID}
Content-Type: application/json
```

### Body (OpenAI-compatible)

```json
{
  "model": "gpt://{folder_id}/yandexgpt-5-lite",
  "temperature": 0.3,
  "max_tokens": 2048,
  "messages": [
    { "role": "system", "content": "<SYSTEM_PROMPT>" },
    { "role": "user", "content": "<user text>" }
  ]
}
```

### Response

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "<JSON string from model>"
      }
    }
  ]
}
```

Модель иногда оборачивает JSON в ` ```json ... ``` ` — снять обёртку перед парсингом (как `_extract_response` в десктопе).

## System prompt: correct

```
Ты — профессиональный редактор и корректор русского языка.
Твоя задача: исправить все орфографические, пунктуационные и грамматические ошибки в тексте,
сохранив оригинальный смысл и стиль автора.

ПРАВИЛА:
1. Исправляй только реальные ошибки, не меняй авторский стиль.
2. Если ошибок нет — верни текст без изменений.
3. Для каждой ошибки укажи: оригинальный фрагмент, исправленный вариант, тип ошибки.

ФОРМАТ ОТВЕТА (строго JSON):
{"corrected_text": "...", "errors": [{"original": "...", "corrected": "...", "type": "spelling|grammar|punctuation|typo", "explanation": "..."}]}

Если ошибок нет, верни: {"corrected_text": "<оригинальный текст>", "errors": []}

Ответь ТОЛЬКО JSON, без markdown-обёрток и пояснений.
```

## System prompt: improve

```
Ты — профессиональный стилист и редактор русского языка.
Твоя задача: предложить улучшенные версии текста в разных стилях.

ПРАВИЛА:
1. Сохрани смысл, но улучши выразительность и структуру.
2. Каждый вариант должен быть самостоятельным и готовым к использованию.

ФОРМАТ ОТВЕТА (строго JSON):
{"suggestions": [
  {"style": "formal", "label": "Формальный стиль", "text": "...", "short_description": "..."},
  {"style": "concise", "label": "Кратко", "text": "...", "short_description": "..."},
  {"style": "creative", "label": "Творческий", "text": "...", "short_description": "..."}
]}

Ответь ТОЛЬКО JSON, без markdown-обёрток и пояснений.
```

## JSON → модели

### CorrectionResult

| Поле | Тип | Описание |
|------|-----|----------|
| `corrected_text` | string | Исправленный текст |
| `errors` | array | Список ошибок |
| `errors[].original` | string | Было |
| `errors[].corrected` | string | Стало |
| `errors[].type` | enum | `spelling`, `grammar`, `punctuation`, `typo`, `style` |
| `errors[].explanation` | string | Пояснение |

`has_changes = (original_text != corrected_text)`

### ImprovementResult

| Поле | Тип |
|------|-----|
| `suggestions` | array |
| `suggestions[].style` | `formal`, `concise`, `creative`, … |
| `suggestions[].label` | string (UI) |
| `suggestions[].text` | string |
| `suggestions[].short_description` | string |

## Ошибки HTTP

| Код | Смысл |
|-----|--------|
| 401 | Неверный ключ / folder / нет доступа к модели |
| 404 | Модель недоступна |
| 429 | Rate limit — retry с backoff |

## Retry (десктоп)

- `max_retries: 2`, `retry_delay_s: 1.0` — перенести в Android client.

## Секреты на Android

Не `.env`. Хранить `YANDEX_API_KEY` и `YANDEX_FOLDER_ID` в EncryptedSharedPreferences. Ввод — экран настроек приложения.
