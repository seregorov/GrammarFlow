"""
GrammarFlow — Менеджер буфера обмена.

Читает и записывает текст в системный буфер обмена.
Сохраняет предыдущее содержимое для возможности отката.
На Windows Qt-clipboard иногда не отдаёт данные другим процессам —
поэтому запись дублируем через pyperclip (Win32 CF_UNICODETEXT).
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QClipboard, QGuiApplication
from PySide6.QtCore import QObject, Signal, QMimeData

from models import normalize_newlines

logger = logging.getLogger(__name__)


def _pyperclip_copy(text: str) -> bool:
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception as exc:
        logger.warning("pyperclip.copy failed: %s", exc)
        return False


def _pyperclip_paste() -> Optional[str]:
    try:
        import pyperclip

        return pyperclip.paste()
    except Exception as exc:
        logger.warning("pyperclip.paste failed: %s", exc)
        return None


class ClipboardManager(QObject):
    """Менеджер буфера обмена с сохранением предыдущего состояния."""

    clipboard_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._saved_clipboard: str = ""
        self._app = QApplication.instance() or QGuiApplication.instance()

    def _qclipboard(self) -> QClipboard:
        if self._app is None:
            raise RuntimeError("QApplication is required for ClipboardManager")
        return self._app.clipboard()

    def read_text(self) -> str:
        """Прочитать текущий текст из буфера обмена."""
        text = self._qclipboard().text(QClipboard.Mode.Clipboard) or ""
        if not text:
            pasted = _pyperclip_paste()
            if pasted:
                text = pasted
        text = normalize_newlines(text)
        if text:
            logger.debug("Clipboard read: %d chars", len(text))
        return text

    def save_and_replace(self, new_text: str) -> None:
        """
        Сохранить текущее содержимое буфера и заменить на new_text.
        Используется перед вставкой исправленного текста.
        """
        self._saved_clipboard = self.read_text()
        self.set_text(new_text)
        logger.info(
            "Clipboard saved (%d chars) and replaced (%d chars)",
            len(self._saved_clipboard),
            len(new_text),
        )

    def restore(self) -> None:
        """Вернуть сохранённое содержимое буфера обмена."""
        if self._saved_clipboard:
            self.set_text(self._saved_clipboard)
            logger.info("Clipboard restored (%d chars)", len(self._saved_clipboard))

    def set_text(self, text: str) -> None:
        """Установить текст в системный буфер (Qt + Win32/pyperclip)."""
        clipboard = self._qclipboard()
        # Явный MimeData надёжнее setText на части конфигураций Windows
        mime = QMimeData()
        mime.setText(text)
        clipboard.setMimeData(mime, QClipboard.Mode.Clipboard)
        # Дублируем через Win32 — иначе Ctrl+V в другом приложении
        # иногда видит старое значение при Qt delayed rendering.
        if not _pyperclip_copy(text):
            clipboard.setText(text, QClipboard.Mode.Clipboard)
        logger.debug("Clipboard set: %d chars", len(text))

    @property
    def saved_clipboard(self) -> str:
        """Вернуть ранее сохранённое содержимое."""
        return self._saved_clipboard

    @property
    def is_empty(self) -> bool:
        """Пуст ли буфер обмена."""
        return not bool(self.read_text())
