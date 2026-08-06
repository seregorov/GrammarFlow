"""
GrammarFlow — Full editor («наушник» шире).

Сегмент Исправить|Варианты, якорь у bubble, stale suggestions, локальные шорткаты.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QPainter, QKeySequence, QTextCursor, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTextEdit, QSizePolicy, QSizeGrip,
)

from clipboard_manager import ClipboardManager
from api_client import LlmApiClient
from models import (
    ApiResponse, CorrectionResult, ImprovementResult, RewriteSuggestion,
)
from .theme import Colors, prepare_frameless_overlay, fade_window
from .highlight import apply_correction_highlights, clear_highlights
from .components import (
    WindowTitleBar, ModeSegment, RefreshButton, SuggestionCard,
    LoadingOverlay, Toast,
)

logger = logging.getLogger(__name__)

CARD_COLORS = {
    "formal": QColor(99, 102, 241),
    "concise": QColor(16, 185, 129),
    "creative": QColor(244, 114, 182),
}


class MainWindow(QWidget):
    collapse_requested = Signal()
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
        self._suggestions: list[RewriteSuggestion] = []
        self._active_mode = "correct"  # correct | improve
        self._cards: list[SuggestionCard] = []
        self._suggestions_baseline = ""
        self._suppress_text_changed = False
        self._suggestions_stale = False
        self._highlights_on = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(640, 560)
        self.resize(720, 680)

        prepare_frameless_overlay(self)
        self.setWindowOpacity(1.0)
        self._build_ui()
        self._setup_shortcuts()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(0)

        self._container = QFrame()
        self._container.setObjectName("mainContainer")
        self._container.setStyleSheet(
            f"#mainContainer {{"
            f"  background-color: rgba(22, 30, 46, 248);"
            f"  border: 1px solid rgba(255,255,255,30);"
            f"  border-radius: 16px;"
            f"}}"
        )
        outer = QVBoxLayout(self._container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = WindowTitleBar("GrammarFlow", show_back=True)
        self._header.back_requested.connect(self.collapse_requested.emit)
        self._header.minimize_requested.connect(self.minimize_requested.emit)
        self._header.close_requested.connect(self.close_requested.emit)
        outer.addWidget(self._header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,20); border: none;")
        outer.addWidget(sep)

        content = QWidget()
        content_l = QVBoxLayout(content)
        content_l.setContentsMargins(16, 14, 16, 10)
        content_l.setSpacing(12)

        hotkeys_hint = QLabel(
            "Alt+C открыть · Ctrl+Enter исправить · "
            "Ctrl+Shift+Enter варианты · Ctrl+R буфер · Esc назад"
        )
        hotkeys_hint.setWordWrap(True)
        hotkeys_hint.setStyleSheet(
            f"color: {Colors.TEXT_DIMMED.name()}; font-size: 11px; font-weight: 500;"
        )
        content_l.addWidget(hotkeys_hint)

        self._mode_segment = ModeSegment()
        self._mode_segment.correct_clicked.connect(self._on_auto_correct)
        self._mode_segment.improve_clicked.connect(self._on_suggest_improve)
        content_l.addWidget(self._mode_segment)

        # Editor + refresh
        editor_head = QHBoxLayout()
        editor_lbl = QLabel("Текст — можно править здесь или обновить из буфера")
        editor_lbl.setStyleSheet(
            f"color: {Colors.TEXT_DIMMED.name()}; font-size: 11px; font-weight: 500;"
        )
        editor_head.addWidget(editor_lbl)
        editor_head.addStretch()
        self._btn_refresh = RefreshButton()
        self._btn_refresh.setToolTip("Обновить из буфера (Ctrl+R)")
        self._btn_refresh.clicked.connect(self.refresh_from_clipboard)
        editor_head.addWidget(self._btn_refresh)
        content_l.addLayout(editor_head)

        self._text_editor = QTextEdit()
        self._text_editor.setPlaceholderText("Введите или вставьте текст…")
        self._text_editor.setAcceptRichText(False)
        self._text_editor.setMinimumHeight(160)
        self._text_editor.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._text_editor.textChanged.connect(self._on_editor_text_changed)
        content_l.addWidget(self._text_editor, stretch=4)

        # Suggestions panel — softer chrome
        self._sug_panel = QFrame()
        self._sug_panel.setObjectName("sugPanel")
        self._sug_panel.setStyleSheet(
            f"#sugPanel {{"
            f"  background: rgba(10, 16, 28, 120);"
            f"  border: 1px solid rgba(255,255,255,18);"
            f"  border-radius: 12px;"
            f"}}"
        )
        self._sug_panel.setMinimumHeight(160)
        self._sug_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        sug_l = QVBoxLayout(self._sug_panel)
        sug_l.setContentsMargins(12, 10, 12, 10)
        sug_l.setSpacing(8)

        sug_head = QHBoxLayout()
        self._sug_title = QLabel("Варианты")
        self._sug_title.setStyleSheet(
            f"color: {Colors.TEXT_MUTED.name()}; font-size: 11px; font-weight: 600;"
        )
        sug_head.addWidget(self._sug_title)
        sug_head.addStretch()
        sug_l.addLayout(sug_head)

        self._cards_row = QHBoxLayout()
        self._cards_row.setSpacing(10)
        self._show_suggestions_placeholder(
            "Нажмите «Варианты» или Ctrl+Shift+Enter"
        )
        sug_l.addLayout(self._cards_row, stretch=1)
        content_l.addWidget(self._sug_panel, stretch=2)

        footer = QHBoxLayout()
        self._status_bar = QLabel("")
        self._status_bar.setStyleSheet(
            f"color: {Colors.TEXT_DIMMED.name()}; font-size: 11px;"
        )
        footer.addWidget(self._status_bar, stretch=1)
        grip = QSizeGrip(self._container)
        grip.setFixedSize(14, 14)
        footer.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom)
        content_l.addLayout(footer)

        outer.addWidget(content, stretch=1)
        root.addWidget(self._container)

        self._loader = LoadingOverlay(self._container)
        self._loader.hide()
        self._toast = Toast("", parent=self._container)
        self._toast.hide()

        self._set_active_mode("correct")

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self, self._on_auto_correct)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self._on_auto_correct)
        QShortcut(QKeySequence("Ctrl+Shift+Return"), self, self._on_suggest_improve)
        QShortcut(QKeySequence("Ctrl+Shift+Enter"), self, self._on_suggest_improve)
        QShortcut(QKeySequence("Ctrl+R"), self, self.refresh_from_clipboard)

    def _set_active_mode(self, mode: str) -> None:
        self._active_mode = mode
        self._mode_segment.set_active(mode)

    def _clear_highlights(self) -> None:
        self._highlights_on = False
        clear_highlights(self._text_editor)

    def show_main(
        self,
        initial_text: str = "",
        *,
        focus_mode: str = "correct",
        anchor: QPoint | None = None,
        auto_run: bool = False,
    ) -> None:
        self._suppress_text_changed = True
        if initial_text is not None:
            self._text_editor.setPlainText(initial_text)
            self._original_text = initial_text
        self._suggestions_baseline = self._text_editor.toPlainText()
        self._suggestions_stale = False
        self._clear_highlights()
        self._clear_cards()
        self._show_suggestions_placeholder(
            "Нажмите «Варианты» или Ctrl+Shift+Enter"
        )
        self._suppress_text_changed = False

        self._set_active_mode(
            focus_mode if focus_mode in ("correct", "improve") else "correct"
        )

        if anchor is not None:
            self._position_near_anchor(anchor)
        else:
            self._position_near_cursor()

        fade_window(self, show=True)
        self._text_editor.setFocus()
        cursor = self._text_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text_editor.setTextCursor(cursor)

        if auto_run and focus_mode == "improve":
            self._on_suggest_improve()
        elif auto_run and focus_mode == "correct":
            self._on_auto_correct()

    def _position_near_anchor(self, anchor: QPoint) -> None:
        x, y = anchor.x(), anchor.y()
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

    def _position_near_cursor(self) -> None:
        from PySide6.QtGui import QCursor
        pos = QCursor.pos()
        self._position_near_anchor(QPoint(pos.x() + 20, pos.y() + 20))

    def hide_main(self) -> None:
        fade_window(self, show=False, on_finished=lambda: self.hidden.emit())

    def refresh_from_clipboard(self) -> None:
        text = self._clipboard.read_text()
        self._suppress_text_changed = True
        self._text_editor.setPlainText(text)
        self._original_text = text
        self._suggestions_baseline = text
        self._suppress_text_changed = False
        self._clear_highlights()
        self._mark_suggestions_stale(clear=True)
        self._update_status("Текст обновлён из буфера")

    def _update_status(self, text: str) -> None:
        self._status_bar.setText(text)

    def _on_editor_text_changed(self) -> None:
        if self._suppress_text_changed:
            return
        if self._highlights_on:
            self._clear_highlights()
        if not self._suggestions and not self._suggestions_stale:
            return
        current = self._text_editor.toPlainText()
        if current != self._suggestions_baseline:
            self._mark_suggestions_stale(clear=True)

    def _mark_suggestions_stale(self, *, clear: bool = True) -> None:
        self._suggestions_stale = True
        self._suggestions = []
        if clear:
            self._clear_cards()
            self._show_suggestions_placeholder(
                "Текст изменился — обновите варианты (Ctrl+Shift+Enter)"
            )
        self._update_status("Текст изменился — обновите варианты")

    def _show_suggestions_placeholder(self, message: str) -> None:
        ph = QLabel(message)
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setWordWrap(True)
        ph.setStyleSheet(
            f"color: {Colors.TEXT_DIMMED.name()}; font-size: 13px; padding: 24px;"
        )
        self._cards_row.addWidget(ph)

    def _on_auto_correct(self) -> None:
        self._set_active_mode("correct")
        text = self._text_editor.toPlainText().strip()
        if not text:
            return
        self._original_text = text
        self._clear_highlights()
        self._loader.show_loading()
        self._mode_segment.setEnabled(False)
        self._update_status("Анализ…")
        self._api.correct_text(text, self._on_correction_result)

    def _on_suggest_improve(self) -> None:
        self._set_active_mode("improve")
        text = self._text_editor.toPlainText().strip()
        if not text:
            return
        self._original_text = text
        self._loader.show_loading()
        self._mode_segment.setEnabled(False)
        self._update_status("Генерация вариантов…")
        self._api.improve_text(text, self._on_improvement_result)

    def _on_correction_result(self, response: ApiResponse) -> None:
        self._loader.hide_loading()
        self._mode_segment.setEnabled(True)

        if not response.success or not isinstance(response.data, CorrectionResult):
            self._update_status(f"Ошибка: {response.error_message}")
            return

        result: CorrectionResult = response.data
        if result.has_changes:
            self._suppress_text_changed = True
            n = apply_correction_highlights(
                self._text_editor,
                corrected_text=result.corrected_text,
                errors=result.errors,
                original_text=result.original_text or self._original_text,
            )
            self._suggestions_baseline = result.corrected_text
            self._suppress_text_changed = False
            self._highlights_on = True
            self._original_text = result.corrected_text
            self._corrected_text = result.corrected_text
            self._clipboard.save_and_replace(result.corrected_text)
            self.text_replaced.emit(result.corrected_text)
            err_n = len(result.errors) or n or 1
            self._update_status(
                f"Исправлено {err_n} · подсвечено {n} · {response.latency_ms}ms"
            )
            self._toast._message = f"Исправлено {err_n}"
            self._toast._color = Colors.SUCCESS
            self._place_toast()
            self._toast.show_toast()
        else:
            self._clear_highlights()
            self._update_status(f"Ошибок не найдено · {response.latency_ms}ms")

    def _on_improvement_result(self, response: ApiResponse) -> None:
        self._loader.hide_loading()
        self._mode_segment.setEnabled(True)

        if not response.success or not isinstance(response.data, ImprovementResult):
            self._update_status(f"Ошибка: {response.error_message}")
            return

        result: ImprovementResult = response.data
        self._suggestions = result.suggestions
        self._suggestions_baseline = self._text_editor.toPlainText()
        self._suggestions_stale = False
        self._display_suggestions(result.suggestions)
        self._update_status(
            f"Варианты загружены · {len(result.suggestions)} · {response.latency_ms}ms"
        )

    def _clear_cards(self) -> None:
        while self._cards_row.count():
            item = self._cards_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._cards.clear()

    def _display_suggestions(self, suggestions: list[RewriteSuggestion]) -> None:
        self._clear_cards()

        if not suggestions:
            self._show_suggestions_placeholder("Нет предложений")
            return

        for i, sug in enumerate(suggestions):
            accent = CARD_COLORS.get(sug.style.value, Colors.ACCENT)
            card = SuggestionCard(
                style_label=sug.label,
                description=sug.short_description,
                text=sug.text,
                accent_color=accent,
                selected=(i == 0),
                compact=True,
            )
            card.clicked.connect(self._on_suggestion_clicked)
            self._cards.append(card)
            self._cards_row.addWidget(card, stretch=1)

    def _on_suggestion_clicked(self, text: str) -> None:
        for card in self._cards:
            card.set_selected(card._suggestion_text == text)
        self._suppress_text_changed = True
        self._text_editor.setPlainText(text)
        self._suggestions_baseline = text
        self._suppress_text_changed = False
        self._clipboard.save_and_replace(text)
        self.text_replaced.emit(text)
        self._update_status("Выбран вариант | Текст скопирован")
        self._toast._message = "Текст скопирован"
        self._toast._color = Colors.SUCCESS
        self._place_toast()
        self._toast.show_toast()

    def _place_toast(self) -> None:
        self._toast.setFixedSize(max(140, self._container.width() - 32), 36)
        self._toast.move(16, max(8, self._container.height() - 56))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._loader.isVisible():
            self._loader.setGeometry(self._container.rect())
        if self._toast.isVisible():
            self._place_toast()

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
        for grow, alpha in ((7, 16), (3, 28)):
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(r.adjusted(-grow, -grow, grow, grow), 16, 16)
        painter.end()
