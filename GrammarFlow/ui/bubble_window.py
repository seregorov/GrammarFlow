"""
GrammarFlow — Floating Bubble («наушник» у курсора).

Редактируемый текст, локальные шорткаты, без дублирующей стрелки expand.
Исправить → применить текст + буфер; Правки → подсветка мест ошибок.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QPainter, QColor, QCursor, QKeySequence, QTextCursor, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSizePolicy, QSizeGrip, QTextEdit,
)

from clipboard_manager import ClipboardManager
from api_client import LlmApiClient
from models import ApiResponse, CorrectionResult, TextError, normalize_newlines
from .theme import Colors, prepare_frameless_overlay, set_font, fade_window
from .highlight import apply_correction_highlights, clear_highlights
from .components import (
    WindowTitleBar, PrimaryButton, GhostButton, LoadingOverlay, RefreshButton,
    ICON_WAND, ICON_SPARKLES,
)

logger = logging.getLogger(__name__)


class BubbleWindow(QWidget):
    expand_requested = Signal()
    text_replaced = Signal(str)
    minimize_requested = Signal()
    close_requested = Signal()
    hidden = Signal()

    def __init__(
        self,
        clipboard: ClipboardManager,
        api_client: LlmApiClient,
        parent=None,
    ):
        super().__init__(parent)
        self._clipboard = clipboard
        self._api = api_client
        self._original_text = ""
        self._corrected_text = ""
        self._errors: list[TextError] = []
        self._pending_result: CorrectionResult | None = None
        self._highlights_on = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(360, 520)
        self.resize(420, 580)

        prepare_frameless_overlay(self)
        self.setWindowOpacity(1.0)
        self._build_ui()
        self._setup_shortcuts()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(0)

        self._container = QFrame()
        self._container.setObjectName("bubbleContainer")
        self._container.setStyleSheet(
            f"#bubbleContainer {{"
            f"  background-color: rgba(22, 30, 46, 245);"
            f"  border: 1px solid rgba(255,255,255,30);"
            f"  border-radius: 14px;"
            f"}}"
        )
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = WindowTitleBar("GrammarFlow")
        self._header.minimize_requested.connect(self.minimize_requested.emit)
        self._header.close_requested.connect(self.close_requested.emit)
        layout.addWidget(self._header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,28); border: none;")
        layout.addWidget(sep)

        body = QWidget()
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 12, 14, 8)
        body_layout.setSpacing(10)

        preview_row = QHBoxLayout()
        preview_lbl = QLabel("ТЕКСТ")
        set_font(preview_lbl, size=11, weight=600)
        preview_lbl.setStyleSheet(f"color: {Colors.TEXT_DIMMED.name()};")
        preview_row.addWidget(preview_lbl)
        preview_row.addStretch()
        self._btn_refresh = RefreshButton()
        self._btn_refresh.setToolTip("Обновить из буфера (Ctrl+R)")
        self._btn_refresh.clicked.connect(self.refresh_from_clipboard)
        preview_row.addWidget(self._btn_refresh)
        body_layout.addLayout(preview_row)

        self._preview_card = QFrame()
        self._preview_card.setObjectName("previewCard")
        self._preview_card.setMinimumHeight(220)
        self._preview_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_card.setStyleSheet(
            f"#previewCard {{"
            f"  background-color: rgba(10, 16, 28, 250);"
            f"  border: 1px solid rgba(255,255,255,24);"
            f"  border-radius: 10px;"
            f"}}"
        )
        card_layout = QVBoxLayout(self._preview_card)
        card_layout.setContentsMargins(4, 4, 4, 4)

        self._text_editor = QTextEdit()
        self._text_editor.setPlaceholderText(
            "Вставьте текст (Alt+C) или наберите здесь…"
        )
        self._text_editor.setAcceptRichText(False)
        self._text_editor.setFrameShape(QFrame.Shape.NoFrame)
        self._text_editor.setMinimumHeight(200)
        self._text_editor.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._text_editor.setStyleSheet(
            f"QTextEdit {{"
            f"  background: transparent;"
            f"  color: {Colors.TEXT_PRIMARY.name()};"
            f"  border: none;"
            f"  padding: 8px;"
            f"  font-size: 14px;"
            f"}}"
        )
        self._text_editor.textChanged.connect(self._on_editor_text_changed)
        card_layout.addWidget(self._text_editor)
        body_layout.addWidget(self._preview_card, stretch=1)

        self._error_badge = QLabel("")
        self._error_badge.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._error_badge.setStyleSheet(
            f"color: {Colors.ERROR.name()}; font-size: 12px;"
        )
        body_layout.addWidget(self._error_badge)

        self._btn_correct = PrimaryButton("Исправить", ICON_WAND)
        self._btn_correct.setToolTip("Исправить орфографию (Ctrl+Enter)")
        self._btn_correct.clicked.connect(self._on_auto_correct)
        body_layout.addWidget(self._btn_correct)

        self._btn_review = GhostButton("Правки", badge_count=0)
        self._btn_review.setToolTip("Показать, где были ошибки (подсветка)")
        self._btn_review.setEnabled(False)
        self._btn_review.clicked.connect(self._on_review_corrections)
        body_layout.addWidget(self._btn_review)

        self._btn_improve = GhostButton("Варианты", ICON_SPARKLES)
        self._btn_improve.setToolTip("Открыть варианты улучшения (Ctrl+Shift+Enter)")
        self._btn_improve.clicked.connect(self._on_suggest_improve)
        body_layout.addWidget(self._btn_improve)

        layout.addWidget(body, stretch=1)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 0, 8, 8)
        footer_layout.addStretch()
        grip = QSizeGrip(self._container)
        grip.setFixedSize(14, 14)
        footer_layout.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(footer)

        root.addWidget(self._container)

        self._loader = LoadingOverlay(self._container)
        self._loader.hide()
        self._suppress_text_changed = False

    def _on_editor_text_changed(self) -> None:
        if self._suppress_text_changed:
            return
        if self._pending_result is not None:
            expected = self._pending_result.corrected_text
            if self._text_editor.toPlainText() != expected:
                self._clear_pending()
                self._error_badge.setText("Текст изменился — повторите Исправить")
                self._error_badge.setStyleSheet(
                    f"color: {Colors.TEXT_MUTED.name()}; font-size: 12px;"
                )

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self, self._on_auto_correct)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self._on_auto_correct)
        QShortcut(QKeySequence("Ctrl+Shift+Return"), self, self._on_suggest_improve)
        QShortcut(QKeySequence("Ctrl+Shift+Enter"), self, self._on_suggest_improve)
        QShortcut(QKeySequence("Ctrl+R"), self, self.refresh_from_clipboard)

    def current_text(self) -> str:
        """Актуальный текст из редактора."""
        return self._text_editor.toPlainText()

    def anchor_point(self) -> QPoint:
        """Точка якоря для full-окна (левый верх bubble)."""
        return self.frameGeometry().topLeft()

    def show_bubble(self, text: str | None = None) -> None:
        """Показать bubble. text=None → читать clipboard."""
        if text is None:
            text = self._clipboard.read_text()
        self._apply_text(text)
        self._position_near_cursor()
        fade_window(self, show=True)
        self._text_editor.setFocus()
        cursor = self._text_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text_editor.setTextCursor(cursor)

    def hide_bubble(self) -> None:
        fade_window(self, show=False, on_finished=lambda: self.hidden.emit())

    def refresh_from_clipboard(self) -> None:
        """Явно подтянуть текст из буфера (не затирает ручной ввод без спроса)."""
        text = self._clipboard.read_text()
        self._apply_text(text)
        self._error_badge.setText("Обновлено из буфера")
        self._error_badge.setStyleSheet(
            f"color: {Colors.SUCCESS.name()}; font-size: 12px;"
        )

    def _clear_pending(self) -> None:
        self._pending_result = None
        self._highlights_on = False
        self._btn_review.setEnabled(False)
        self._btn_review.set_badge(0)
        clear_highlights(self._text_editor)

    def _apply_text(self, text: str) -> None:
        self._original_text = normalize_newlines(text or "")
        self._corrected_text = ""
        self._errors = []
        self._btn_review.set_badge(0)
        self._error_badge.setText("")
        self._clear_pending()
        self._suppress_text_changed = True
        self._text_editor.setPlainText(self._original_text)
        self._suppress_text_changed = False

    def _on_auto_correct(self) -> None:
        text = normalize_newlines(self.current_text()).strip()
        if not text:
            return
        self._original_text = text
        self._clear_pending()
        self._loader.show_loading()
        self._btn_correct.setEnabled(False)
        self._api.correct_text(text, self._on_correction_result)

    def _on_suggest_improve(self) -> None:
        self._original_text = self.current_text()
        self.expand_requested.emit()

    def _on_correction_result(self, response: ApiResponse) -> None:
        self._loader.hide_loading()
        self._btn_correct.setEnabled(True)

        if not response.success or not isinstance(response.data, CorrectionResult):
            msg = response.error_message or "Ошибка API"
            short = msg if len(msg) < 90 else msg[:87] + "…"
            self._error_badge.setText(f"✕  {short}")
            self._error_badge.setStyleSheet(
                f"color: {Colors.ERROR.name()}; font-size: 12px;"
            )
            return

        result: CorrectionResult = response.data
        if result.has_changes:
            self._pending_result = result
            self._errors = result.errors
            self._corrected_text = result.corrected_text
            self._original_text = result.corrected_text

            self._suppress_text_changed = True
            self._text_editor.setPlainText(result.corrected_text)
            clear_highlights(self._text_editor)
            self._suppress_text_changed = False
            self._highlights_on = False

            self._clipboard.save_and_replace(result.corrected_text)
            self.text_replaced.emit(result.corrected_text)

            self._btn_review.setEnabled(True)
            # Сразу показать где правки (кнопка Правки — toggle)
            self._suppress_text_changed = True
            n_hl = apply_correction_highlights(
                self._text_editor,
                corrected_text=result.corrected_text,
                errors=result.errors,
                original_text=result.original_text,
            )
            self._suppress_text_changed = False
            self._highlights_on = True
            shown = n_hl or len(result.errors)
            if shown <= 0:
                # Текст отличается, но видимых правок нет (редкий край)
                self._btn_review.set_badge(0)
                self._error_badge.setText("Текст обновлён")
            else:
                self._btn_review.set_badge(min(shown, 9))
                self._error_badge.setText(
                    f"Исправлено {shown} · подсвечено {n_hl}"
                )
            self._error_badge.setStyleSheet(
                f"color: {Colors.SUCCESS.name()}; font-size: 12px;"
            )
        else:
            self._pending_result = None
            self._btn_review.setEnabled(False)
            self._btn_review.set_badge(0)
            self._error_badge.setText("Ошибок не найдено")
            self._error_badge.setStyleSheet(
                f"color: {Colors.SUCCESS.name()}; font-size: 12px;"
            )

    def _on_review_corrections(self) -> None:
        if self._highlights_on:
            clear_highlights(self._text_editor)
            self._highlights_on = False
            self._error_badge.setText("Подсветка снята")
            self._error_badge.setStyleSheet(
                f"color: {Colors.TEXT_MUTED.name()}; font-size: 12px;"
            )
            return

        result = self._pending_result
        if result is None or not result.has_changes:
            return

        self._suppress_text_changed = True
        n = apply_correction_highlights(
            self._text_editor,
            corrected_text=result.corrected_text,
            errors=result.errors,
            original_text=result.original_text,
        )
        self._suppress_text_changed = False
        self._highlights_on = True
        self._error_badge.setText(
            f"Показано {n} правок" if n else "Изменения подсвечены"
        )
        self._error_badge.setStyleSheet(
            f"color: {Colors.SUCCESS.name()}; font-size: 12px;"
        )

    def _position_near_cursor(self) -> None:
        pos = QCursor.pos()
        x, y = pos.x() + 20, pos.y() + 20
        screen = self.screen().availableGeometry()
        if x + self.width() > screen.right():
            x = screen.right() - self.width() - 10
        if y + self.height() > screen.bottom():
            y = screen.bottom() - self.height() - 10
        if x < screen.left():
            x = screen.left() + 10
        if y < screen.top():
            y = screen.top() + 10
        self.move(x, y)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._loader.isVisible():
            self._loader.setGeometry(self._container.rect())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = (
            self._container.geometry()
            if hasattr(self, "_container")
            else self.rect().adjusted(10, 10, -10, -10)
        )
        painter.setPen(Qt.PenStyle.NoPen)
        for grow, alpha in ((6, 18), (3, 28)):
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(r.adjusted(-grow, -grow, grow, grow), 14, 14)
        painter.end()
