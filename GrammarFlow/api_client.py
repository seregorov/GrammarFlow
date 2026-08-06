"""
GrammarFlow — API-клиент для LLM.

Единый интерфейс для OpenAI-совместимых провайдеров (Yandex AI Studio, OpenRouter, …).
Содержит системные промпты для коррекции грамматики и стилистического улучшения.
Взаимодействие с API происходит в отдельном потоке через QThread.
"""

from __future__ import annotations

import json
import logging
import time
import random
from typing import Optional

import httpx
from PySide6.QtCore import QThread, Signal

from config import LLMConfig, OPENROUTER_FREE_MODELS
from models import (
    ApiResponse,
    CorrectionResult,
    ImprovementResult,
    RewriteSuggestion,
    RewriteStyle,
    TextError,
    ErrorType,
)

logger = logging.getLogger(__name__)


# ======================================================================
# Системные промпты
# ======================================================================

SYSTEM_PROMPT_CORRECT = """\
Ты — профессиональный редактор и корректор русского языка. \n
Твоя задача: исправить все орфографические, пунктуационные и грамматические ошибки в тексте, \n
сохранив оригинальный смысл и стиль автора. \n
\n
ПРАВИЛА:\n
1. Исправляй только реальные ошибки, не меняй авторский стиль.\n
2. Если ошибок нет — верни текст без изменений.\n
3. Для каждой ошибки укажи: оригинальный фрагмент, исправленный вариант, тип ошибки.\n
\n
ФОРМАТ ОТВЕТА (строго JSON):\n
{"corrected_text": "...", "errors": [{"original": "...", "corrected": "...", "type": "spelling|grammar|punctuation|typo", "explanation": "..."}]}

Если ошибок нет, верни: {"corrected_text": "<оригинальный текст>", "errors": []}\n
\n
Ответь ТОЛЬКО JSON, без markdown-обёрток и пояснений.
"""

SYSTEM_PROMPT_IMPROVE = """\
Ты — профессиональный стилист и редактор русского языка. \n
Твоя задача: предложить улучшенные версии текста в разных стилях. \n
\n
ПРАВИЛА:\n
1. Сохрани смысл, но улучши выразительность и структуру.\n
2. Каждый вариант должен быть самостоятельным и готовым к использованию.\n
\n
ФОРМАТ ОТВЕТА (строго JSON):\n
{"suggestions": [\n
  {"style": "formal", "label": "Формальный стиль", "text": "...", "short_description": "..."},\n
  {"style": "concise", "label": "Кратко", "text": "...", "short_description": "..."},\n
  {"style": "creative", "label": "Творческий", "text": "...", "short_description": "..."}\n
]}\n
\n
Ответь ТОЛЬКО JSON, без markdown-обёрток и пояснений.
"""


# ======================================================================
# Рабочий поток для API-запросов (не блокирует UI)
# ======================================================================

class _ApiWorker(QThread):
    """Фоновый поток для выполнения API-запроса."""

    finished = Signal(ApiResponse)

    def __init__(
        self,
        config: LLMConfig,
        system_prompt: str,
        user_text: str,
        parse_mode: str = "correct",  # "correct" | "improve"
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self._system_prompt = system_prompt
        self._user_text = user_text
        self._parse_mode = parse_mode

    def run(self) -> None:
        start = time.monotonic()
        try:
            result = self._call_api()
            latency = int((time.monotonic() - start) * 1000)
            result.latency_ms = latency
            self.finished.emit(result)
        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            self.finished.emit(ApiResponse(
                success=False,
                error_message=str(exc),
                provider=self._config.provider,
                latency_ms=latency,
            ))

    # ------------------------------------------------------------------
    # Внутренняя логика
    # ------------------------------------------------------------------

    def _model_uri(self) -> str:
        """Полный URI модели для Yandex; иначе значение из конфига."""
        model = (self._config.model or "").strip()
        if "://" in model:
            return model
        if self._config.provider == "yandex":
            folder = (self._config.folder_id or "").strip()
            if not folder:
                raise ValueError("Не задан folder_id для Yandex AI Studio")
            return f"gpt://{folder}/{model}"
        return model

    def _build_payload(self) -> dict:
        """Сформировать тело запроса в формате OpenAI-compatible API."""
        return {
            "model": self._model_uri(),
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": self._user_text},
            ],
        }

    def _build_headers(self) -> dict:
        """Сформировать HTTP-заголовки в зависимости от провайдера."""
        headers = {"Content-Type": "application/json"}

        if self._config.provider == "yandex":
            headers["Authorization"] = f"Api-Key {self._config.api_key}"
            folder = (self._config.folder_id or "").strip()
            if folder:
                headers["x-folder-id"] = folder
            return headers

        if self._config.provider == "openrouter":
            # OpenRouter: Bearer + обязательные идентификационные заголовки
            headers["Authorization"] = f"Bearer {self._config.api_key}"
            headers["HTTP-Referer"] = self._config.http_referer
            headers["X-Title"] = self._config.app_title
            return headers

        if self._config.provider == "openai":
            headers["Authorization"] = f"Bearer {self._config.api_key}"
            return headers

        if self._config.provider == "gemini":
            headers["Authorization"] = f"Bearer {self._config.api_key}"
            return headers

        if self._config.provider == "ollama":
            # Локальный — без авторизации
            return headers

        return headers

    def _build_url(self) -> str:
        """Определить endpoint URL."""
        if self._config.provider == "ollama":
            return f"{self._config.base_url}/api/chat"
        return f"{self._config.base_url.rstrip('/')}/chat/completions"

    def _auth_error_message(self, status: int) -> str:
        if self._config.provider == "yandex":
            return (
                f"HTTP {status}: неверный API-ключ, folder_id или нет доступа к модели. "
                f"Проверьте ключ и каталог в https://aistudio.yandex.ru/"
            )
        if self._config.provider == "openrouter":
            return (
                f"HTTP {status}: неверный API-ключ или нет доступа. "
                f"Получите ключ на https://openrouter.ai/keys"
            )
        return f"HTTP {status}: ошибка авторизации или доступа к API"

    def _call_api(self) -> ApiResponse:
        """Выполнить HTTP-запрос к API провайдеру с retry и fallback."""
        headers = self._build_headers()
        url = self._build_url()
        payload = self._build_payload()

        # ---- Retry loop ----
        last_exc: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                logger.debug(
                    "API attempt %d/%d → %s [%s]",
                    attempt,
                    self._config.max_retries,
                    self._config.provider,
                    payload.get("model", self._config.model),
                )
                with httpx.Client(timeout=self._config.timeout) as client:
                    response = client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                return self._extract_response(data)

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                body = exc.response.text[:500]
                logger.warning("HTTP %d on attempt %d: %s", status, attempt, body)

                # 429 — rate limit, подождать подольше
                if status == 429 and attempt < self._config.max_retries:
                    wait = self._config.retry_delay_s * attempt * 3
                    logger.info("Rate limited, waiting %.1fs…", wait)
                    time.sleep(wait)
                    continue

                # 404 — модель снята: дальше fallback, retry бессмысленен
                if status == 404:
                    logger.warning("Model unavailable (404): %s", payload.get("model"))
                    break

                # 401/403 — нет смысла retry
                if status in (401, 403):
                    return ApiResponse(
                        success=False,
                        error_message=self._auth_error_message(status),
                        provider=self._config.provider,
                    )

                # 5xx — серверная ошибка, можно retry
                if status >= 500 and attempt < self._config.max_retries:
                    time.sleep(self._config.retry_delay_s * attempt)
                    continue

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                logger.warning("Network error on attempt %d: %s", attempt, exc)
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_delay_s * attempt)
                    continue

            # Неизвестная ошибка — пробуем ещё раз
            if attempt < self._config.max_retries:
                time.sleep(self._config.retry_delay_s * attempt)
                continue

        # Fallback только для OpenRouter free-моделей
        if self._config.provider == "openrouter" and self._config.model.endswith(":free"):
            fallback_result = self._try_fallback(headers, payload)
            if fallback_result:
                return fallback_result

        return ApiResponse(
            success=False,
            error_message=(
                f"Все попытки исчерпаны ({self._config.max_retries}). "
                f"Последняя ошибка: {last_exc}"
            ),
            provider=self._config.provider,
        )

    def _try_fallback(self, headers: dict, payload: dict) -> Optional[ApiResponse]:
        """
        Если текущая free-модель недоступна, попробовать другую free-модель
        из каталога OPENROUTER_FREE_MODELS.
        """
        fallback_candidates = [
            model_id
            for model_id, info in OPENROUTER_FREE_MODELS.items()
            if model_id != self._config.model
               and model_id.endswith(":free")
        ]
        random.shuffle(fallback_candidates)

        for fallback_model in fallback_candidates[:3]:  # до 3 альтернатив
            try:
                logger.info("Fallback → %s", fallback_model)
                payload["model"] = fallback_model
                url = self._build_url()

                with httpx.Client(timeout=self._config.timeout) as client:
                    response = client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                result = self._extract_response(data)
                result.provider = f"{self._config.provider} ({fallback_model})"
                logger.info("Fallback %s succeeded", fallback_model)
                return result

            except Exception as exc:
                logger.warning("Fallback %s failed: %s", fallback_model, exc)
                continue

        return None

    def _extract_response(self, data: dict) -> ApiResponse:
        """Извлечь и распарсить контент из JSON-ответа API."""
        # Безопасное извлечение (защита от нестандартных форматов)
        try:
            choices = data.get("choices", [])
            if not choices:
                return ApiResponse(
                    success=False,
                    error_message="Пустой ответ от модели (no choices)",
                    provider=self._config.provider,
                )
            content = choices[0].get("message", {}).get("content", "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            return ApiResponse(
                success=False,
                error_message=f"Неверный формат ответа: {exc}",
                provider=self._config.provider,
            )

        # Убрать возможные markdown-обёртки ```json ... ```
        for prefix in ("```json", "```", ):
            if content.startswith(prefix):
                content = content[len(prefix):]
                break
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Попытка извлечь JSON из ответа (модель могла обернуть в текст)
        json_match = self._extract_json(content)
        if json_match:
            content = json_match

        # Парсинг
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            return ApiResponse(
                success=False,
                error_message=f"Модель вернула невалидный JSON: {exc}. Ответ: {content[:200]}",
                provider=self._config.provider,
            )

        if self._parse_mode == "correct":
            return self._parse_correction(parsed)
        else:
            return self._parse_improvement(parsed)

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """
        Попытаться найти JSON-объект в тексте,
        даже если модель добавила пояснения вокруг.
        """
        import re
        # Ищем первый { и последний }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
            # Проверяем, что это валидный JSON
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        return None

    def _parse_correction(self, data: dict) -> ApiResponse:
        """Распарсить результат коррекции."""
        errors = []
        for e in data.get("errors", []):
            try:
                errors.append(TextError(
                    original=e["original"],
                    corrected=e["corrected"],
                    error_type=ErrorType(e.get("type", "spelling")),
                    explanation=e.get("explanation", ""),
                ))
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed error entry: %s", exc)

        result = CorrectionResult(
            original_text=self._user_text,
            corrected_text=data.get("corrected_text", self._user_text),
            errors=errors,
        )
        return ApiResponse(
            success=True,
            data=result,
            provider=self._config.provider,
        )

    def _parse_improvement(self, data: dict) -> ApiResponse:
        """Распарсить результат улучшения текста."""
        suggestions = []
        for s in data.get("suggestions", []):
            try:
                suggestions.append(RewriteSuggestion(
                    style=RewriteStyle(s["style"]),
                    label=s["label"],
                    text=s["text"],
                    short_description=s.get("short_description", ""),
                ))
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed suggestion: %s", exc)

        result = ImprovementResult(
            original_text=self._user_text,
            suggestions=suggestions,
        )
        return ApiResponse(
            success=True,
            data=result,
            provider=self._config.provider,
        )


# ======================================================================
# Публичный фасад API-клиента
# ======================================================================

class LlmApiClient:
    """
    Фасад для взаимодействия с LLM API.
    Все запросы выполняются в фоновых потоках через QThread.
    Результаты доставляются через Qt-сигналы.
    """

    def __init__(self, config: LLMConfig, parent=None):
        self._config = config
        self._parent = parent
        self._active_worker: Optional[_ApiWorker] = None

    def correct_text(self, text: str, callback) -> Optional[_ApiWorker]:
        """
        Отправить текст на авто-исправление.
        callback(response: ApiResponse) будет вызван по завершении.
        Возвращает рабочий поток или None если текст пуст.
        """
        if not text.strip():
            return None

        self._cancel_active()
        worker = _ApiWorker(
            config=self._config,
            system_prompt=SYSTEM_PROMPT_CORRECT,
            user_text=text,
            parse_mode="correct",
            parent=self._parent,
        )
        worker.finished.connect(callback)
        self._active_worker = worker
        worker.start()
        return worker

    def improve_text(self, text: str, callback) -> Optional[_ApiWorker]:
        """
        Запросить варианты стилистического улучшения текста.
        callback(response: ApiResponse) будет вызван по завершении.
        """
        if not text.strip():
            return None

        self._cancel_active()
        worker = _ApiWorker(
            config=self._config,
            system_prompt=SYSTEM_PROMPT_IMPROVE,
            user_text=text,
            parse_mode="improve",
            parent=self._parent,
        )
        worker.finished.connect(callback)
        self._active_worker = worker
        worker.start()
        return worker

    def _cancel_active(self) -> None:
        """Отменить активный запрос, если есть."""
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.terminate()
            self._active_worker.wait(2000)
            self._active_worker = None
