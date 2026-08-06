"""
GrammarFlow — Тема Windows 11 Dark (Fluent), редизайн под референс.
Fade окон — только через windowOpacity, без QGraphicsOpacityEffect.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QFont, QPalette
from PySide6.QtWidgets import QWidget, QStyleFactory, QApplication


def css(color: QColor) -> str:
    """
    QColor → CSS. Важно: QColor.name() отбрасывает alpha,
    поэтому BORDER/BG_HOVER превращались в сплошной #ffffff.
    """
    r, g, b, a = color.red(), color.green(), color.blue(), color.alpha()
    if a >= 255:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgba({r}, {g}, {b}, {a})"


class Colors:
    """Палитра под референс: тёмный slate + Blue accent."""

    BG_WINDOW = QColor(22, 30, 46, 235)
    BG_SURFACE = QColor(15, 23, 42, 200)
    BG_HOVER = QColor(255, 255, 255, 22)
    BG_CARD = QColor(30, 41, 59, 220)
    BG_INPUT = QColor(12, 18, 32, 230)
    BG_PREVIEW = QColor(10, 16, 28, 240)

    ACCENT = QColor(59, 130, 246)
    ACCENT_HOVER = QColor(37, 99, 235)
    ACCENT_LIGHT = QColor(96, 165, 250)
    ACCENT_GLOW = QColor(59, 130, 246, 90)

    TEXT_PRIMARY = QColor(248, 250, 252)
    TEXT_SECONDARY = QColor(226, 232, 240)
    TEXT_MUTED = QColor(148, 163, 184)
    TEXT_DIMMED = QColor(100, 116, 139)
    TEXT_CHROME = QColor(226, 232, 240)

    ERROR = QColor(239, 68, 68)
    SUCCESS = QColor(34, 197, 94)
    WARNING = QColor(245, 158, 11)

    GRADIENT_START = QColor(6, 182, 212)
    GRADIENT_END = QColor(59, 130, 246)

    BORDER = QColor(255, 255, 255, 28)
    BORDER_FOCUS = QColor(96, 165, 250, 200)


def enable_mica_background(window: QWidget, fallback_blur: bool = True) -> None:
    """Mica на Win11; иначе полупрозрачный фон."""
    if sys.platform == "win32":
        try:
            import ctypes

            hwnd = int(window.winId())
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)
            )
            mica = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 38, ctypes.byref(mica), ctypes.sizeof(mica)
            )
            return
        except Exception:
            pass
    if fallback_blur:
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def prepare_frameless_overlay(window: QWidget) -> None:
    """
    Прозрачный прямоугольный HWND вокруг скруглённого UI.
    Без этого Win/Qt заливает поля чёрным квадратом.
    Mica здесь не используем — конфликтует с rounded + margins.
    """
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    window.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
    window.setAutoFillBackground(False)
    window.setObjectName("framelessOverlay")
    # Только корень — иначе transparent протечёт на кнопки/карточки
    window.setStyleSheet("#framelessOverlay { background: transparent; border: none; }")



def fade_window(
    window: QWidget,
    *,
    show: bool,
    duration_ms: int = 180,
    on_finished=None,
) -> QPropertyAnimation | None:
    """Показать/скрыть окно через windowOpacity (без GraphicsEffect)."""
    # Stop previous fade if any
    prev = getattr(window, "_fade_anim", None)
    if prev is not None:
        try:
            prev.stop()
        except RuntimeError:
            pass

    if show:
        # Уже видно — не мигать opacity 0→1 при refresh
        if window.isVisible() and window.windowOpacity() >= 0.95:
            window.setWindowOpacity(1.0)
            window.raise_()
            window.activateWindow()
            return None

        window.setWindowOpacity(0.0)
        window.show()
        window.raise_()
        window.activateWindow()
        anim = QPropertyAnimation(window, b"windowOpacity", window)
        anim.setDuration(duration_ms)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        window._fade_anim = anim  # type: ignore[attr-defined]
        return anim

    anim = QPropertyAnimation(window, b"windowOpacity", window)
    anim.setDuration(duration_ms)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.setStartValue(max(0.0, float(window.windowOpacity())))
    anim.setEndValue(0.0)

    def _hide():
        window.hide()
        window.setWindowOpacity(1.0)
        if on_finished:
            on_finished()

    anim.finished.connect(_hide)
    anim.start()
    window._fade_anim = anim  # type: ignore[attr-defined]
    return anim


QSS_GLOBAL = f"""
QWidget {{
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    font-size: 14px;
    color: {css(Colors.TEXT_SECONDARY)};
}}

QPushButton {{
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 500;
    font-size: 13px;
    color: {css(Colors.TEXT_PRIMARY)};
    background: transparent;
    outline: none;
}}
QPushButton:hover {{
    background: {css(Colors.BG_HOVER)};
}}
QPushButton:pressed {{
    background: rgba(255, 255, 255, 28);
}}
QPushButton:focus {{
    outline: none;
    border: none;
}}
QPushButton:disabled {{
    color: {css(Colors.TEXT_DIMMED)};
}}

QPushButton#primaryBtn {{
    background: {css(Colors.ACCENT)};
    color: #FFFFFF;
    font-weight: 600;
    border-radius: 10px;
    border: 1px solid {css(Colors.ACCENT)};
    min-height: 42px;
    outline: none;
}}
QPushButton#primaryBtn:hover {{
    background: {css(Colors.ACCENT_HOVER)};
    border: 1px solid {css(Colors.ACCENT_HOVER)};
}}
QPushButton#primaryBtn:pressed {{
    background: {css(Colors.ACCENT_HOVER)};
    border: 1px solid {css(Colors.ACCENT_HOVER)};
}}
QPushButton#primaryBtn:focus {{
    outline: none;
    background: {css(Colors.ACCENT)};
    border: 1px solid {css(Colors.ACCENT)};
}}
QPushButton#primaryBtn:disabled {{
    background: rgba(59, 130, 246, 90);
    border: 1px solid transparent;
}}

QPushButton#ghostBtn {{
    background: {css(Colors.BG_SURFACE)};
    border: 1px solid rgba(148, 163, 184, 70);
    border-radius: 10px;
    min-height: 40px;
    outline: none;
}}
QPushButton#ghostBtn:hover {{
    border: 1px solid rgba(96, 165, 250, 160);
    background: rgba(59, 130, 246, 36);
}}
QPushButton#ghostBtn:pressed {{
    border: 1px solid rgba(96, 165, 250, 200);
    background: rgba(59, 130, 246, 56);
}}
QPushButton#ghostBtn:focus {{
    outline: none;
    border: 1px solid rgba(148, 163, 184, 70);
    background: {css(Colors.BG_SURFACE)};
}}
QPushButton#ghostBtn:disabled {{
    color: {css(Colors.TEXT_DIMMED)};
    background: {css(Colors.BG_SURFACE)};
    border: 1px solid rgba(100, 116, 139, 50);
}}

QPushButton#chromeBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
    color: {css(Colors.TEXT_CHROME)};
    min-width: 32px;
    min-height: 28px;
    padding: 0;
    outline: none;
}}
QPushButton#chromeBtn:hover {{
    background: rgba(255, 255, 255, 18);
    border: none;
}}
QPushButton#chromeBtn:focus {{
    outline: none;
    background: transparent;
    border: none;
}}
QPushButton#chromeClose:hover {{
    background: {css(Colors.ERROR)};
    color: #FFFFFF;
    border: none;
}}
QPushButton#chromeClose:focus {{
    outline: none;
    background: transparent;
    border: none;
    color: {css(Colors.TEXT_CHROME)};
}}

QTextEdit, QTextBrowser {{
    background: {css(Colors.BG_INPUT)};
    color: {css(Colors.TEXT_PRIMARY)};
    border: 1px solid rgba(255, 255, 255, 16);
    border-radius: 10px;
    padding: 14px;
    font-size: 15px;
    line-height: 1.45;
    selection-background-color: {css(Colors.ACCENT)};
    selection-color: #FFFFFF;
}}
QTextEdit:focus, QTextBrowser:focus {{
    border-color: {css(Colors.BORDER_FOCUS)};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 4px 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 22);
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 40);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QLabel {{
    background: transparent;
    border: none;
}}

QMenu {{
    background-color: #161e2e;
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 28);
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    background: transparent;
    color: #f8fafc;
    padding: 8px 28px 8px 16px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: rgba(59, 130, 246, 180);
    color: #ffffff;
}}
QMenu::item:disabled {{
    color: #64748b;
}}
QMenu::separator {{
    height: 1px;
    background: rgba(255, 255, 255, 24);
    margin: 4px 8px;
}}
"""


def apply_theme(app_or_widget) -> None:
    """Fusion + тёмная палитра: Windows native style рисует белую обводку фокуса."""
    if isinstance(app_or_widget, QApplication):
        fusion = QStyleFactory.create("Fusion")
        if fusion is not None:
            app_or_widget.setStyle(fusion)
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, Colors.BG_WINDOW)
        palette.setColor(QPalette.ColorRole.WindowText, Colors.TEXT_PRIMARY)
        palette.setColor(QPalette.ColorRole.Base, Colors.BG_INPUT)
        palette.setColor(QPalette.ColorRole.Text, Colors.TEXT_PRIMARY)
        palette.setColor(QPalette.ColorRole.Button, Colors.BG_SURFACE)
        palette.setColor(QPalette.ColorRole.ButtonText, Colors.TEXT_PRIMARY)
        palette.setColor(QPalette.ColorRole.Highlight, Colors.ACCENT)
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Light, Colors.BG_SURFACE)
        palette.setColor(QPalette.ColorRole.Midlight, Colors.BG_CARD)
        palette.setColor(QPalette.ColorRole.Dark, Colors.BG_WINDOW)
        palette.setColor(QPalette.ColorRole.Mid, Colors.BG_CARD)
        palette.setColor(QPalette.ColorRole.Shadow, QColor(0, 0, 0))
        app_or_widget.setPalette(palette)
    app_or_widget.setStyleSheet(QSS_GLOBAL)


def set_font(widget, size: int = 14, weight: int = 400, family: str | None = None) -> None:
    font = QFont(family or "Segoe UI Variable", size)
    font.setWeight(QFont.Weight(weight))
    widget.setFont(font)


class AcrylicWidget(QWidget):
    """Простой rounded-фон без graphics effects."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_color = Colors.BG_WINDOW
        self._border_radius = 14

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), self._border_radius, self._border_radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(Colors.BORDER)
        painter.drawRoundedRect(
            self.rect().adjusted(0, 0, -1, -1), self._border_radius, self._border_radius
        )
        painter.end()
