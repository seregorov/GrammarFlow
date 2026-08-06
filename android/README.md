# GrammarFlow Android

Мобильная версия GrammarFlow — **клавиатура (IME)** с кнопками **Исправить** и **Варианты** над клавишами. Правка русского текста прямо в поле ввода, без отдельного «блокнота с вставкой».

Десктоп-клиент (Windows, PySide6) живёт в [`../GrammarFlow/`](../GrammarFlow/). Android — **новый клиент** к тому же AI-ядру (Yandex AI Studio).

## Статус

Реализованы фазы 1–5 roadmap (личное использование, без Play):

- Gradle app `com.grammarflow.keyboard`
- Settings: API Key / Folder ID, Ping, онбординг, удаление ключей
- IME: RU/EN/символы, Исправить → превью с подсветкой → Применить
- Варианты (improve) — sheet с карточками
- Process Text / Share → correct → копировать

## Сборка

Нужны Android Studio (или JDK 17 + Android SDK).

```bash
cd android
./gradlew :app:assembleDebug
# Windows: gradlew.bat :app:assembleDebug
```

APK: `app/build/outputs/apk/debug/app-debug.apk`

1. Установить APK  
2. Открыть GrammarFlow → ввести Yandex API Key и Folder ID → **Ping API**  
3. Пройти онбординг / **Открыть настройки клавиатур** → включить GrammarFlow Keyboard  
4. В любом поле ввода выбрать эту клавиатуру

## Документация (AI Docs)

| Файл | О чём |
|------|--------|
| [docs/00-why.md](docs/00-why.md) | Зачем Android, почему IME |
| [docs/01-stack.md](docs/01-stack.md) | Стек |
| [docs/02-ux-ime.md](docs/02-ux-ime.md) | UX |
| [docs/03-api-contract.md](docs/03-api-contract.md) | Промпты / JSON |
| [docs/04-roadmap.md](docs/04-roadmap.md) | Roadmap |
| [docs/05-constraints-privacy.md](docs/05-constraints-privacy.md) | Privacy |

Для AI-агентов: [AGENTS.md](AGENTS.md).

## Связь с десктопом

- Общие: системные промпты, JSON-схемы, модель `yandexgpt-5-lite`, endpoint Yandex AI Studio.
- Разные: UX (IME vs Alt+C), секреты (EncryptedSharedPreferences vs `.env`).
