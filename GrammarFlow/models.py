"""
GrammarFlow — Модели данных.

Определяет структуры для текстовых ошибок, предложений по улучшению
и результатов коррекции, которыми обмениваются UI и API-слой.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ErrorType(Enum):
    """Тип обнаруженной ошибки."""
    SPELLING = "spelling"
    GRAMMAR = "grammar"
    PUNCTUATION = "punctuation"
    STYLE = "style"
    TYPO = "typo"


class RewriteStyle(Enum):
    """Стиль переписывания текста."""
    FORMAL = "formal"
    CONCISE = "concise"
    CREATIVE = "creative"
    ACADEMIC = "academic"
    FRIENDLY = "friendly"


@dataclass
class TextError:
    """Одна обнаруженная ошибка в тексте."""
    original: str
    corrected: str
    error_type: ErrorType
    start_pos: int = 0
    end_pos: int = 0
    explanation: str = ""


@dataclass
class CorrectionResult:
    """Результат авто-исправления."""
    original_text: str
    corrected_text: str
    errors: list[TextError] = field(default_factory=list)
    has_changes: bool = False

    def __post_init__(self):
        self.has_changes = self.original_text != self.corrected_text


@dataclass
class RewriteSuggestion:
    """Одно предложение по переписыванию текста."""
    style: RewriteStyle
    label: str
    text: str
    short_description: str = ""


@dataclass
class ImprovementResult:
    """Результат анализа улучшений (несколько вариантов переписывания)."""
    original_text: str
    suggestions: list[RewriteSuggestion] = field(default_factory=list)


@dataclass
class ApiResponse:
    """Обёртка над ответом LLM API."""
    success: bool
    data: Optional[CorrectionResult | ImprovementResult] = None
    error_message: str = ""
    provider: str = ""
    latency_ms: int = 0
