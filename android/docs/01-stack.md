# Стек и инструменты

## Выбранный стек

| Компонент | Технология | Зачем |
|-----------|------------|--------|
| Язык | **Kotlin** | Стандарт Android, IME API |
| Клавиатура | **`InputMethodService`** | Системная точка входа для IME |
| UI (settings, панели) | **Jetpack Compose** | Быстрая вёрстка action bar, sheets, onboarding |
| HTTP | **OkHttp** или **Ktor** | OpenAI-compatible chat/completions к Yandex |
| JSON | **kotlinx.serialization** или Moshi | Парсинг ответов LLM |
| Секреты | **EncryptedSharedPreferences** / Keystore | API key + folder_id (не `.env` в APK) |
| Асинхронность | **Kotlin Coroutines** | Запросы к API без блокировки UI |
| DI (по мере роста) | Hilt | Опционально с фазы 2 |

## LLM (как на десктопе)

- **Provider:** Yandex AI Studio
- **Base URL:** `https://ai.api.cloud.yandex.net/v1`
- **Endpoint:** `POST /chat/completions`
- **Model:** `yandexgpt-5-lite`
- **Model URI в теле:** `gpt://{folder_id}/yandexgpt-5-lite`
- **Headers:**
  - `Authorization: Api-Key {YANDEX_API_KEY}`
  - `x-folder-id: {folder_id}`
  - `Content-Type: application/json`

Дефолты и промпты — в [03-api-contract.md](03-api-contract.md), источник — [`../../GrammarFlow/api_client.py`](../../GrammarFlow/api_client.py).

## Явно не использовать

| Не использовать | Причина |
|-----------------|---------|
| PySide6 / Qt | Не целевой стек для Android IME |
| Python на устройстве | Тяжёлый runtime, нет IME API |
| pynput | Только desktop |
| `.env` в репо | Секреты в Keystore |
| Фоновое чтение clipboard | Ограничено Android 10+ |

## Структура проекта (будущая)

```text
android/
├── app/
│   └── src/main/
│       ├── java/.../ime/          # InputMethodService, KeyboardView
│       ├── java/.../api/          # LlmClient, prompts
│       ├── java/.../settings/     # Compose Activity
│       └── java/.../processtext/  # ProcessText Activity (фаза 5)
├── docs/                          # AI Docs (текущая папка)
└── README.md
```

Gradle-модуль создаётся на **фазе 1** roadmap — см. [04-roadmap.md](04-roadmap.md).

## Минимальные версии (ориентир)

- **minSdk:** 26 (Android 8) — EncryptedSharedPreferences, стабильный IME
- **targetSdk:** последний stable (34+)
- **compileSdk:** как targetSdk

## Зависимости (ориентир для Gradle)

```kotlin
// Compose BOM
// androidx.inputmethod
// okhttp / ktor-client
// androidx.security:security-crypto (EncryptedSharedPreferences)
// kotlinx-serialization-json
```

Точные версии зафиксировать при создании `build.gradle.kts` в фазе 1.
