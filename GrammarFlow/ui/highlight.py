"""
GrammarFlow — подсветка исправленных фрагментов в QTextEdit.
"""

from __future__ import annotations

import difflib
from typing import Iterable

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from models import TextError
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


def _minimal_corrected_span(original: str, corrected: str) -> str:
    """
  Минимальный фрагмент corrected, который отличается от original.
  «Как дила всем» / «Как дела всем» → «дела», не вся строка.
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
        return corrected.strip()
    return corrected[start:end]


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
    """Подсветить только изменённые фрагменты (орфография / пунктуация)."""
    spans: list[tuple[int, int]] = []
    occupied: list[tuple[int, int]] = []
    search_from = 0

    for err in errors:
        fragment = _minimal_corrected_span(err.original, err.corrected)
        if not fragment:
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
    """Подсветить только вставки/замены посимвольно (не целые слова/строки)."""
    if not corrected or original == corrected:
        return []

    matcher = difflib.SequenceMatcher(a=original, b=corrected, autojunk=False)
    spans: list[tuple[int, int]] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag not in ("replace", "insert") or j1 >= j2:
            continue
        spans.append((j1, j2))
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
    Возвращает число подсвеченных фрагментов.
    """
    editor.setPlainText(corrected_text)

    spans = _spans_from_errors(corrected_text, errors)
    if not spans and original_text:
        spans = _spans_from_diff(original_text, corrected_text)

    bg = QColor(Colors.SUCCESS)
    bg.setAlpha(90)

    selections: list[QTextEdit.ExtraSelection] = []
    for start, end in spans:
        sel = _make_selection(editor, start, end - start, bg)
        if sel is not None:
            selections.append(sel)

    editor.setExtraSelections(selections)
    return len(selections)
