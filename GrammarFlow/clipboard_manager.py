"""
GrammarFlow — Менеджер буфера обмена.

Читает и записывает текст в системный буфер обмена.
Сохраняет предыдущее содержимое для возможности отката.
Использует PySide6 QClipboard как основной механизм,
с fallback на pyperclip для не-Qt контекстов.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class ClipboardManager(QObject):
    """Менеджер буфера обмена с сохранением предыдущего состояния."""

    # Сигнал, если буфер изменился извне (для будущей реакции)
    clipboard_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._saved_clipboard: str = ""
        self._app = QApplication.instance()

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    def read_text(self) -> str:
        """Прочитать текущий текст из буфера обмена."""
        clipboard = self._app.clipboard()
        text = clipboard.text()
        if text:
            logger.debug("Clipboard read: %d chars", len(text))
        return text or ""

    def save_and_replace(self, new_text: str) -> None:
        """
        Сохранить текущее содержимое буфера и заменить на new_text.
        Используется перед вставкой исправленного текста.
        """
        clipboard = self._app.clipboard()
        self._saved_clipboard = clipboard.text() or ""
        clipboard.setText(new_text)
        logger.info(
            "Clipboard saved (%d chars) and replaced (%d chars)",
            len(self._saved_clipboard),
            len(new_text),
        )

    def restore(self) -> None:
        """Вернуть сохранённое содержимое буфера обмена."""
        if self._saved_clipboard:
            clipboard = self._app.clipboard()
            clipboard.setText(self._saved_clipboard)
            logger.info("Clipboard restored (%d chars)", len(self._saved_clipboard))

    def set_text(self, text: str) -> None:
        """Установить текст в буфер обмена без сохранения предыдущего."""
        clipboard = self._app.clipboard()
        clipboard.setText(text)
        logger.debug("Clipboard set: %d chars", len(text))

    @property
    def saved_clipboard(self) -> str:
        """Вернуть ранее сохранённое содержимое."""
        return self._saved_clipboard

    @property
    def is_empty(self) -> bool:
        """Пуст ли буфер обмена."""
        return not bool(self._app.clipboard().text())
