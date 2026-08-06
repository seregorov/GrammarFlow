# AGENTS — GrammarFlow Android

Инструкции для AI при работе над Android-клиентом.

## Цель продукта

GrammarFlow Keyboard — IME с action bar **Исправить** / **Варианты**. Текст на сервер уходит **только по явному нажатию**, не при каждом нажатии клавиши.

## Не делать

- Не портировать PySide6, Python, `pynput`, system tray, floating bubble как на Windows.
- Не тащить `.env` в репозиторий; секреты — EncryptedSharedPreferences / Keystore.
- Не логировать содержимое полей ввода и нажатия клавиш.
- Не обещать паритет с Gboard (свайп, голос, темы) в MVP.

## Делать

- Читать [docs/03-api-contract.md](docs/03-api-contract.md) — промпты и JSON 1:1 с десктопом [`../GrammarFlow/api_client.py`](../GrammarFlow/api_client.py).
- IME: `InputMethodService`, замена текста через `InputConnection`.
- UI панелей/settings: Jetpack Compose.
- HTTP: OkHttp или Ktor, OpenAI-compatible chat/completions.
- Подсветка правок: spans в превью (аналог [`../GrammarFlow/ui/highlight.py`](../GrammarFlow/ui/highlight.py)).
- ProcessText — вторичный вход, не замена IME.

## Источники правды

1. `android/docs/` — продукт и roadmap
2. `GrammarFlow/api_client.py`, `models.py` — контракт LLM
3. `GrammarFlow/config.py` — дефолт модели `yandexgpt-5-lite`

## Порядок реализации

Следовать [docs/04-roadmap.md](docs/04-roadmap.md): scaffold → IME MVP → highlight + варианты → onboarding → ProcessText.
