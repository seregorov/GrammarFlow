"""
GrammarFlow — подсветка исправленных фрагментов в QTextEdit.
"""

from __future__ import annotations

import difflib
from typing import Iterable

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from models import TextError, normalize_newlines
from .theme import Colors


def clear_highlights(editor: QTextEdit) -> None:
    """Снять ExtraSelection-подсветку."""
    editor.setExtraSelections([])


def _make_selection(
    editor: QTextEdit,
    start: int,
    length: int,
    bg: QColor,
) -> QTextEdit.ExtraSelection | None:
    if length <= 0 or start < 0:
        return None
    cursor = editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
    sel = QTextEdit.ExtraSelection()
    sel.cursor = cursor
    fmt = QTextCharFormat()
    fmt.setBackground(bg)
    sel.format = fmt
    return sel


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch in ("-", "‐", "‑", "'", "’", "ё", "Ё")


def _is_whitespace_only(s: str) -> bool:
    return (not s) or s.isspace()


def _expand_to_word(text: str, start: int, end: int) -> tuple[int, int]:
    """Расширить спан до границ слова — иначе «п» из пробе/робе подсветит не ту букву."""
    if not text or start < 0 or end > len(text) or start > end:
        return start, end
    while start > 0 and _is_word_char(text[start - 1]):
        start -= 1
    while end < len(text) and _is_word_char(text[end]):
        end += 1
    return start, end


def _minimal_corrected_span(original: str, corrected: str) -> str:
    """
    Минимальный фрагмент corrected, который отличается от original.
    Затем расширяем до слова: «робе»/«пробе» → «пробе», не «п».
    """
    if not corrected:
        return ""
    if not original or original == corrected:
        return corrected.strip()

    prefix = 0
    max_prefix = min(len(original), len(corrected))
    while prefix < max_prefix and original[prefix] == corrected[prefix]:
        prefix += 1

    suffix = 0
    max_suffix = min(len(original) - prefix, len(corrected) - prefix)
    while (
        suffix < max_suffix
        and original[len(original) - suffix - 1] == corrected[len(corrected) - suffix - 1]
    ):
        suffix += 1

    start = prefix
    end = len(corrected) - suffix
    if start >= end:
        start, end = 0, len(corrected)

    start, end = _expand_to_word(corrected, start, end)
    fragment = corrected[start:end].strip()
    return fragment or corrected.strip()


def _find_fragment(
    text: str,
    fragment: str,
    *,
    hint: int = -1,
) -> int:
    """Найти fragment в text; при нескольких вхождениях — ближе к hint."""
    if not fragment:
        return -1

    positions: list[int] = []
    start = 0
    while True:
        idx = text.find(fragment, start)
        if idx < 0:
            break
        positions.append(idx)
        start = idx + 1

    if not positions:
        return -1
    if hint < 0 or len(positions) == 1:
        return positions[0]
    return min(positions, key=lambda pos: abs(pos - hint))


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans)
    merged: list[tuple[int, int]] = [ordered[0]]
    for start, end in ordered[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _spans_from_errors(corrected: str, errors: Iterable[TextError]) -> list[tuple[int, int]]:
    """Подсветить исправленные фрагменты из списка errors."""
    spans: list[tuple[int, int]] = []
    occupied: list[tuple[int, int]] = []
    search_from = 0

    for err in errors:
        fragment = _minimal_corrected_span(err.original, err.corrected)
        if not fragment or _is_whitespace_only(fragment):
            continue

        hint = err.start_pos if err.start_pos >= 0 else search_from
        idx = _find_fragment(corrected, fragment, hint=hint)
        if idx < 0:
            idx = _find_fragment(corrected, fragment)
        if idx < 0:
            continue

        end = idx + len(fragment)
        if any(not (end <= a or idx >= b) for a, b in occupied):
            continue

        spans.append((idx, end))
        occupied.append((idx, end))
        search_from = end

    return _merge_spans(spans)


def _spans_from_diff(original: str, corrected: str) -> list[tuple[int, int]]:
    """
    Подсветка по диффу: только смысловые вставки/замены.
    Пробелы и переносы строк не подсвечиваем и не раздуваем до соседних слов.
    """
    original = normalize_newlines(original)
    corrected = normalize_newlines(corrected)
    if not corrected or original == corrected:
        return []

    matcher = difflib.SequenceMatcher(a=original, b=corrected, autojunk=False)
    spans: list[tuple[int, int]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        if tag == "delete":
            # Удаление только пробелов/CR — игнор; иначе стык без раздувания на абзац
            if _is_whitespace_only(original[i1:i2]):
                continue
            if j1 < len(corrected) and _is_word_char(corrected[j1]):
                start, end = _expand_to_word(corrected, j1, j1 + 1)
                spans.append((start, end))
            elif j1 > 0 and _is_word_char(corrected[j1 - 1]):
                start, end = _expand_to_word(corrected, j1 - 1, j1)
                spans.append((start, end))
            continue

        if tag not in ("replace", "insert") or j1 >= j2:
            continue

        new_chunk = corrected[j1:j2]
        old_chunk = original[i1:i2] if tag == "replace" else ""
        # CRLF↔LF / лишние пустые строки — не ошибки
        if _is_whitespace_only(new_chunk) and _is_whitespace_only(old_chunk):
            continue
        if _is_whitespace_only(new_chunk) and tag == "insert":
            continue

        if any(_is_word_char(c) for c in new_chunk):
            start, end = _expand_to_word(corrected, j1, j2)
        else:
            # пунктуация и т.п. — узкий спан, без захвата «Сегодня»
            start, end = j1, j2
        if start < end:
            spans.append((start, end))

    return _merge_spans(spans)


def apply_correction_highlights(
    editor: QTextEdit,
    *,
    corrected_text: str,
    errors: list[TextError],
    original_text: str = "",
) -> int:
    """
    Показать corrected_text и подсветить правки.
    Сначала дифф полного текста (надёжнее), затем errors как запасной путь.
    Возвращает число подсвеченных фрагментов.
    """
    corrected_text = normalize_newlines(corrected_text)
    original_text = normalize_newlines(original_text) if original_text else ""
    editor.setPlainText(corrected_text)

    spans: list[tuple[int, int]] = []
    if original_text and original_text != corrected_text:
        spans = _spans_from_diff(original_text, corrected_text)
    if not spans:
        spans = _spans_from_errors(corrected_text, errors)

    bg = QColor(Colors.SUCCESS)
    bg.setAlpha(110)

    selections: list[QTextEdit.ExtraSelection] = []
    for start, end in spans:
        sel = _make_selection(editor, start, end - start, bg)
        if sel is not None:
            selections.append(sel)

    editor.setExtraSelections(selections)
    return len(selections)
