"""
GrammarFlow — UI-компоненты (редизайн).
Без QGraphicsOpacityEffect на окнах; chrome через QPainter-иконки.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal, Property, QPoint, QRect
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QPixmap, QLinearGradient,
)
from PySide6.QtWidgets import (
    QPushButton, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QSizePolicy,
)

from .theme import Colors, set_font


def _render_svg_icon(svg_text: str, w: int, h: int) -> QPixmap | None:
    try:
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray

        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        if not renderer.isValid():
            return None
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        if not painter.isActive():
            return None
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        return pixmap
    except Exception:
        return None


class _IconButton(QPushButton):
    """Кнопка chrome с иконкой, нарисованной в paintEvent."""

    def __init__(self, kind: str, parent=None):
        super().__init__("", parent)
        self._kind = kind  # min | close | back
        self.setObjectName("chromeClose" if kind == "close" else "chromeBtn")
        self.setFixedSize(34, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        if kind == "min":
            self.setToolTip("Свернуть в трей")
        elif kind == "close":
            self.setToolTip("Закрыть")
        else:
            self.setToolTip("Назад")

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        hover = self.underMouse()
        if self._kind == "close" and hover:
            painter.setBrush(Colors.ERROR)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)
            color = QColor(255, 255, 255)
        elif hover:
            painter.setBrush(QColor(255, 255, 255, 22))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)
            color = Colors.TEXT_CHROME
        else:
            color = Colors.TEXT_CHROME

        pen = QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        r = self.rect().adjusted(11, 9, -11, -9)
        if self._kind == "min":
            y = self.height() // 2
            painter.drawLine(r.left(), y, r.right(), y)
        elif self._kind == "close":
            painter.drawLine(r.topLeft(), r.bottomRight())
            painter.drawLine(r.topRight(), r.bottomLeft())
        else:
            cx, cy = self.width() // 2, self.height() // 2
            painter.drawLine(cx + 4, cy, cx - 5, cy)
            painter.drawLine(cx - 5, cy, cx - 1, cy - 4)
            painter.drawLine(cx - 5, cy, cx - 1, cy + 4)
        painter.end()


class WindowTitleBar(QWidget):
    """Шапка: [back?] logo + title …… min close. Drag окна."""

    minimize_requested = Signal()
    close_requested = Signal()
    back_requested = Signal()

    def __init__(
        self,
        title: str = "GrammarFlow",
        *,
        show_back: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setFixedHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._drag_offset: QPoint | None = None
        self._show_back = show_back
        self._setup_ui(title)

    def _setup_ui(self, title: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 6, 0)
        layout.setSpacing(6)

        if self._show_back:
            self._btn_back = _IconButton("back")
            self._btn_back.clicked.connect(self.back_requested.emit)
            layout.addWidget(self._btn_back)
        else:
            self._btn_back = None

        # spacer for painted logo
        self._logo_space = QWidget()
        self._logo_space.setFixedSize(28, 28)
        layout.addWidget(self._logo_space)

        title_lbl = QLabel(title)
        set_font(title_lbl, size=14, weight=600)
        title_lbl.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        layout.addWidget(title_lbl)
        layout.addStretch()

        self._btn_min = _IconButton("min")
        self._btn_min.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(self._btn_min)

        self._btn_close = _IconButton("close")
        self._btn_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(self._btn_close)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # logo circle under logo_space
        geo = self._logo_space.geometry()
        x, y, size = geo.x(), geo.y() + (geo.height() - 26) // 2, 26
        gradient = QLinearGradient(x, y, x + size, y + size)
        gradient.setColorAt(0, Colors.GRADIENT_START)
        gradient.setColorAt(1, Colors.GRADIENT_END)
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(x, y, size, size)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRect(x, y, size, size), Qt.AlignmentFlag.AlignCenter, "G")
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if isinstance(child, QPushButton) or (
                child is not None and isinstance(child.parentWidget(), QPushButton)
            ):
                super().mousePressEvent(event)
                return
            win = self.window()
            self._drag_offset = (
                event.globalPosition().toPoint() - win.frameGeometry().topLeft()
            )
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class AppHeader(WindowTitleBar):
    def __init__(self, parent=None):
        super().__init__("GrammarFlow", parent=parent)


class PrimaryButton(QPushButton):
    def __init__(self, text: str, icon_svg: str | None = None, parent=None):
        super().__init__("", parent)
        self._label_text = text
        self.setObjectName("primaryBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._text_label: QLabel | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)
        layout.addStretch()

        if icon_svg:
            icon = QLabel()
            icon.setFixedSize(18, 18)
            pix = _render_svg_icon(icon_svg, 18, 18)
            if pix:
                icon.setPixmap(pix)
            layout.addWidget(icon)

        self._text_label = QLabel(text)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setStyleSheet(
            "color: #FFFFFF; font-weight: 600; font-size: 13px; background: transparent;"
        )
        layout.addWidget(self._text_label)
        layout.addStretch()

    def set_loading(self, loading: bool) -> None:
        self.setEnabled(not loading)
        if self._text_label:
            self._text_label.setText("..." if loading else self._label_text)

    def text(self) -> str:
        return self._label_text

    def setText(self, text: str) -> None:
        self._label_text = text
        if self._text_label:
            self._text_label.setText(text)


class GhostButton(QPushButton):
    def __init__(
        self,
        text: str,
        icon_svg: str | None = None,
        badge_count: int = 0,
        parent=None,
    ):
        super().__init__("", parent)
        self._label_text = text
        self.setObjectName("ghostBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._text_label: QLabel | None = None
        self._badge: QLabel | None = None
        self._left_pad: QWidget | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # Pad слева зеркалит badge справа — оба hide/show вместе, иначе сдвиг
        self._left_pad = QWidget()
        self._left_pad.setFixedSize(20, 20)
        layout.addWidget(self._left_pad)

        layout.addStretch()
        if icon_svg:
            icon = QLabel()
            icon.setFixedSize(16, 16)
            pix = _render_svg_icon(icon_svg, 16, 16)
            if pix:
                icon.setPixmap(pix)
            layout.addWidget(icon)

        self._text_label = QLabel(text)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY.name()}; font-size: 13px;"
            " font-weight: 600; background: transparent;"
        )
        layout.addWidget(self._text_label)
        layout.addStretch()

        self._badge = QLabel("")
        self._badge.setFixedSize(20, 20)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            f"background: {Colors.ERROR.name()}; color: #FFFFFF;"
            "border-radius: 10px; font-size: 11px; font-weight: 700;"
        )
        layout.addWidget(self._badge)
        self.set_badge(badge_count)

    def set_badge(self, count: int) -> None:
        if not self._badge:
            return
        if count > 0:
            self._badge.setText(str(count))
            self._badge.show()
            if self._left_pad:
                self._left_pad.show()
        else:
            self._badge.hide()
            if self._left_pad:
                self._left_pad.hide()

    def text(self) -> str:
        return self._label_text

    def setText(self, text: str) -> None:
        self._label_text = text
        if self._text_label:
            self._text_label.setText(text)


class ActionPill(QPushButton):
    """Pill-кнопка (legacy; предпочтительно ModeSegment)."""

    def __init__(self, text: str, icon_svg: str | None = None, parent=None):
        super().__init__("", parent)
        self._label_text = text
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(18, 18)
        self._text_label = QLabel(text)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)
        layout.addStretch()
        if icon_svg:
            pix = _render_svg_icon(icon_svg, 18, 18)
            if pix:
                self._icon_label.setPixmap(pix)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)
        layout.addStretch()
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background: {Colors.ACCENT.name()};"
                f"  border: 1px solid {Colors.ACCENT_LIGHT.name()};"
                f"  border-radius: 10px;"
                f"}}"
                f"QPushButton:hover {{ background: {Colors.ACCENT_HOVER.name()}; }}"
            )
            self._text_label.setStyleSheet(
                "color: #FFFFFF; font-weight: 600; font-size: 12px; background: transparent;"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background: {Colors.BG_SURFACE.name()};"
                f"  border: 1px solid {Colors.BORDER.name()};"
                f"  border-radius: 10px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  border-color: {Colors.ACCENT_LIGHT.name()};"
                f"  background: {Colors.BG_HOVER.name()};"
                f"}}"
            )
            self._text_label.setStyleSheet(
                f"color: {Colors.ACCENT_LIGHT.name()}; font-weight: 500; font-size: 12px;"
                " background: transparent;"
            )


class ModeSegment(QWidget):
    """Компактный сегмент: Исправить | Варианты."""

    correct_clicked = Signal()
    improve_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        wrap = QFrame(self)
        wrap.setObjectName("modeSegment")
        wrap.setStyleSheet(
            f"#modeSegment {{"
            f"  background: {Colors.BG_SURFACE.name()};"
            f"  border: 1px solid {Colors.BORDER.name()};"
            f"  border-radius: 10px;"
            f"}}"
        )
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(wrap)

        row = QHBoxLayout(wrap)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(2)

        self._btn_correct = QPushButton("Исправить")
        self._btn_correct.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_correct.setToolTip("Исправить орфографию (Ctrl+Enter)")
        self._btn_correct.clicked.connect(self.correct_clicked.emit)
        row.addWidget(self._btn_correct, stretch=1)

        self._btn_improve = QPushButton("Варианты")
        self._btn_improve.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_improve.setToolTip("Варианты улучшения (Ctrl+Shift+Enter)")
        self._btn_improve.clicked.connect(self.improve_clicked.emit)
        row.addWidget(self._btn_improve, stretch=1)

        self.set_active("correct")

    def set_active(self, mode: str) -> None:
        for btn, active in (
            (self._btn_correct, mode == "correct"),
            (self._btn_improve, mode == "improve"),
        ):
            if active:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background: {Colors.ACCENT.name()};"
                    f"  color: #FFFFFF;"
                    f"  border: none;"
                    f"  border-radius: 8px;"
                    f"  font-weight: 600;"
                    f"  font-size: 12px;"
                    f"  padding: 6px 10px;"
                    f"  text-align: center;"
                    f"}}"
                    f"QPushButton:hover {{ background: {Colors.ACCENT_HOVER.name()}; }}"
                    f"QPushButton:disabled {{ background: rgba(59,130,246,90); }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background: transparent;"
                    f"  color: {Colors.TEXT_SECONDARY.name()};"
                    f"  border: none;"
                    f"  border-radius: 8px;"
                    f"  font-weight: 500;"
                    f"  font-size: 12px;"
                    f"  padding: 6px 10px;"
                    f"  text-align: center;"
                    f"}}"
                    f"QPushButton:hover {{"
                    f"  background: {Colors.BG_HOVER.name()};"
                    f"  color: {Colors.TEXT_PRIMARY.name()};"
                    f"}}"
                    f"QPushButton:disabled {{ color: {Colors.TEXT_DIMMED.name()}; }}"
                )

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        super().setEnabled(enabled)
        self._btn_correct.setEnabled(enabled)
        self._btn_improve.setEnabled(enabled)


class RefreshButton(QPushButton):
    """Компактная кнопка обновления из буфера."""

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setObjectName("chromeBtn")
        self.setFixedSize(30, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Обновить из буфера обмена")
        self.setFlat(True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.underMouse():
            painter.setBrush(QColor(255, 255, 255, 22))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)
        pen = QPen(Colors.TEXT_CHROME, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() // 2, self.height() // 2
        painter.drawArc(cx - 6, cy - 6, 12, 12, 40 * 16, 280 * 16)
        # arrow tip
        painter.drawLine(cx + 5, cy - 6, cx + 8, cy - 3)
        painter.drawLine(cx + 5, cy - 6, cx + 2, cy - 3)
        painter.end()


class SuggestionCard(QFrame):
    clicked = Signal(str)

    def __init__(
        self,
        style_label: str,
        description: str,
        text: str,
        accent_color: QColor = Colors.ACCENT,
        *,
        selected: bool = False,
        compact: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._suggestion_text = text
        self._accent = accent_color
        self._selected = selected
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.NoFrame)
        if compact:
            self.setMinimumWidth(160)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self._style_lbl = QLabel(style_label)
        self._style_lbl.setStyleSheet(
            f"color: {accent_color.name()}; font-weight: 600; font-size: 12px;"
        )
        top.addWidget(self._style_lbl)
        top.addStretch()
        layout.addLayout(top)

        if description and not compact:
            desc = QLabel(description)
            desc.setStyleSheet(f"color: {Colors.TEXT_DIMMED.name()}; font-size: 11px;")
            desc.setWordWrap(True)
            layout.addWidget(desc)

        body = QLabel(text[:180] + ("..." if len(text) > 180 else ""))
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()}; font-size: 12px;")
        layout.addWidget(body, stretch=1)
        self.set_selected(selected)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        border = self._accent.name() if selected else Colors.BORDER.name()
        self.setStyleSheet(
            f"SuggestionCard {{"
            f"  background: {Colors.BG_CARD.name()};"
            f"  border: 1px solid {border};"
            f"  border-radius: 10px;"
            f"}}"
            f"SuggestionCard:hover {{"
            f"  border-color: {self._accent.name()};"
            f"}}"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._suggestion_text)
        super().mousePressEvent(event)


class LoadingOverlay(QWidget):
    """Оверлей без graphics-effect на родителе окна."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide()

        self._rotation = QPropertyAnimation(self, b"angle")
        self._rotation.setDuration(900)
        self._rotation.setStartValue(0)
        self._rotation.setEndValue(360)
        self._rotation.setLoopCount(-1)
        self._rotation.setEasingCurve(QEasingCurve.Type.Linear)

    def get_angle(self) -> int:
        return self._angle

    def set_angle(self, value: int) -> None:
        self._angle = value
        self.update()

    angle = Property(int, get_angle, set_angle)

    def _sync(self) -> None:
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())

    def show_loading(self) -> None:
        self._sync()
        self.show()
        self.raise_()
        self._rotation.start()

    def hide_loading(self) -> None:
        self._rotation.stop()
        self.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(10, 16, 28, 170))
        painter.save()
        painter.translate(self.width() // 2, self.height() // 2)
        painter.rotate(self._angle)
        pen = QPen(Colors.ACCENT, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(-12, -12, 24, 24, 0, 270 * 16)
        painter.restore()
        painter.end()


class Toast(QWidget):
    def __init__(self, message: str, color: QColor = Colors.SUCCESS, parent=None):
        super().__init__(parent)
        self._message = message
        self._color = color
        self.setFixedHeight(36)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def show_toast(self, duration_ms: int = 2000) -> None:
        self.show()
        self.raise_()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(duration_ms, self.hide)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 8, 8)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._message)
        painter.end()


ICON_WAND = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
    viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round">
    <path d="M15 4V2"/><path d="M15 16v-2"/><path d="M8 9h2"/>
    <path d="M20 9h2"/><path d="M17.8 11.8 19 13"/>
    <path d="M15 9h.01"/><path d="M17.8 6.2 19 5"/>
    <path d="m3 21 9-9"/><path d="M12.2 6.2 11 5"/>
</svg>"""

ICON_SPARKLES = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
    viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round">
    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
    <path d="M5 3v4"/><path d="M19 17v4"/>
    <path d="M3 5h4"/><path d="M17 19h4"/>
</svg>"""

ICON_EXPAND = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"
    viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round">
    <path d="M15 3h6v6"/><path d="M9 21H3v-6"/>
    <path d="m21 3-7 7"/><path d="m3 21 7-7"/>
</svg>"""

ICON_REFRESH = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"
    viewBox="0 0 24 24" fill="none" stroke="#E2E8F0" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round">
    <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
    <path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/>
    <path d="M16 21h5v-5"/>
</svg>"""

ICON_COPY = ""
ICON_CLOSE = ""
