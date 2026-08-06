"""
GrammarFlow — Точка входа.

Оркестрация: Alt+C всегда refresh буфера; hide → mode=hidden;
collapse main → bubble без порчи clipboard.
Improve из bubble → full у якоря bubble + автозапуск API.
"""

from __future__ import annotations

import logging
import signal
import sys

from PySide6.QtWidgets import (
    QApplication, QMessageBox, QSystemTrayIcon, QMenu,
    QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QFormLayout,
)
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QLinearGradient, QFont
from PySide6.QtCore import QTimer, Qt, QLockFile, QDir

from config import AppConfig, ENV_FILE, save_secrets_to_env
from clipboard_manager import ClipboardManager
from hotkey_manager import HotkeyManager
from api_client import LlmApiClient
from ui.theme import apply_theme, Colors
from ui.bubble_window import BubbleWindow
from ui.main_window import MainWindow


def _acquire_single_instance() -> QLockFile | None:
    """Один процесс: иначе Alt+C открывает два bubble подряд."""
    path = QDir.temp().absoluteFilePath("grammarflow-single.lock")
    lock = QLockFile(path)
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        return None
    return lock

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("grammarflow")


def _make_tray_icon() -> QIcon:
    """Контрастная G на круге — несколько размеров для Windows tray."""
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin = max(1, size // 16)
        diameter = size - margin * 2
        gradient = QLinearGradient(margin, margin, margin + diameter, margin + diameter)
        gradient.setColorAt(0, Colors.GRADIENT_START)
        gradient.setColorAt(1, Colors.GRADIENT_END)
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(margin, margin, diameter, diameter)

        font_px = max(8, int(size * 0.55))
        font = QFont("Segoe UI", font_px, QFont.Weight.Bold)
        font.setPixelSize(font_px)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "G")
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class GrammarFlowApp:
    def __init__(self):
        self._config = AppConfig.load()
        logger.info(
            "Config loaded. Provider: %s, Model: %s",
            self._config.llm.provider,
            self._config.llm.model,
        )

        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationName("GrammarFlow")
        apply_theme(self._app)

        self._clipboard = ClipboardManager()
        self._api = LlmApiClient(self._config.llm)
        self._hotkeys = HotkeyManager(self._config.hotkeys)

        self._bubble = BubbleWindow(self._clipboard, self._api)
        self._main_win = MainWindow(self._clipboard, self._api)

        self._mode = "hidden"

        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(3000)
        self._hide_timer.timeout.connect(self._auto_hide)

        self._setup_tray()
        self._connect_signals()

    def _setup_tray(self) -> None:
        self._tray = QSystemTrayIcon(_make_tray_icon(), self._app)
        self._tray.setToolTip("GrammarFlow — Alt+C")

        self._tray_menu = QMenu()
        self._tray_menu.setStyleSheet(
            "QMenu {"
            "  background-color: #161e2e;"
            "  color: #f8fafc;"
            "  border: 1px solid rgba(255,255,255,28);"
            "  border-radius: 8px;"
            "  padding: 4px;"
            "}"
            "QMenu::item {"
            "  background: transparent;"
            "  color: #f8fafc;"
            "  padding: 8px 28px 8px 16px;"
            "  border-radius: 6px;"
            "}"
            "QMenu::item:selected {"
            "  background: rgba(59,130,246,180);"
            "  color: #ffffff;"
            "}"
            "QMenu::separator {"
            "  height: 1px;"
            "  background: rgba(255,255,255,24);"
            "  margin: 4px 8px;"
            "}"
        )
        act_show = QAction("Показать", self._tray_menu)
        act_show.triggered.connect(self._show_from_tray)
        self._tray_menu.addAction(act_show)
        act_hide = QAction("Скрыть окна", self._tray_menu)
        act_hide.triggered.connect(self._minimize_to_tray)
        self._tray_menu.addAction(act_hide)
        self._tray_menu.addSeparator()
        act_quit = QAction("Выход", self._tray_menu)
        act_quit.triggered.connect(self._quit_app)
        self._tray_menu.addAction(act_quit)

        self._tray.setContextMenu(self._tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _connect_signals(self) -> None:
        self._hotkeys.toggle_bubble_triggered.connect(self._on_hotkey_show)
        self._hotkeys.dismiss_triggered.connect(self._dismiss)

        self._bubble.expand_requested.connect(self._switch_to_main)
        self._bubble.text_replaced.connect(self._on_text_replaced)
        self._bubble.minimize_requested.connect(self._minimize_to_tray)
        self._bubble.close_requested.connect(self._minimize_to_tray)
        self._bubble.hidden.connect(self._on_bubble_hidden)

        self._main_win.collapse_requested.connect(self._switch_to_bubble)
        self._main_win.text_replaced.connect(self._on_text_replaced)
        self._main_win.minimize_requested.connect(self._minimize_to_tray)
        self._main_win.close_requested.connect(self._minimize_to_tray)
        self._main_win.hidden.connect(self._on_main_hidden)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self._force_hide(self._main_win)
        self._bubble.show_bubble()
        self._mode = "bubble"

    def _minimize_to_tray(self) -> None:
        self._force_hide(self._bubble)
        self._force_hide(self._main_win)
        self._mode = "hidden"
        if self._tray.supportsMessages():
            self._tray.showMessage(
                "GrammarFlow",
                "Свёрнуто в трей. Alt+C — открыть снова.",
                QSystemTrayIcon.MessageIcon.Information,
                1800,
            )

    def _quit_app(self) -> None:
        self._hotkeys.stop()
        self._tray.hide()
        self._app.quit()

    def _on_hotkey_show(self) -> None:
        """Alt+C: всегда показать bubble и перечитать буфер."""
        logger.info("Alt+C show/refresh (mode=%s)", self._mode)
        self._force_hide(self._main_win)
        self._bubble.show_bubble()  # text=None → read clipboard
        self._mode = "bubble"

    def _on_bubble_hidden(self) -> None:
        if self._mode == "bubble":
            self._mode = "hidden"

    def _on_main_hidden(self) -> None:
        if self._mode == "main":
            self._mode = "hidden"

    def _force_hide(self, window) -> None:
        """Мгновенно скрыть окно, остановив fade — без гонки двух окон."""
        prev = getattr(window, "_fade_anim", None)
        if prev is not None:
            try:
                prev.stop()
            except RuntimeError:
                pass
            window._fade_anim = None
        window.hide()
        window.setWindowOpacity(1.0)

    def _switch_to_main(self) -> None:
        text = self._bubble.current_text()
        anchor = self._bubble.anchor_point()
        self._force_hide(self._bubble)
        # Improve из bubble → full рядом + сразу генерация вариантов
        self._show_main_with_text(
            text,
            focus_mode="improve",
            anchor=anchor,
            auto_run=True,
        )

    def _switch_to_bubble(self) -> None:
        text = self._main_win._text_editor.toPlainText()
        self._force_hide(self._main_win)
        self._show_bubble_with_text(text)

    def _show_main_with_text(
        self,
        text: str,
        *,
        focus_mode: str = "correct",
        anchor=None,
        auto_run: bool = False,
    ) -> None:
        self._force_hide(self._bubble)
        self._main_win.show_main(
            text,
            focus_mode=focus_mode,
            anchor=anchor,
            auto_run=auto_run,
        )
        self._mode = "main"

    def _show_bubble_with_text(self, text: str) -> None:
        # Не трогаем системный clipboard — передаём текст напрямую
        self._force_hide(self._main_win)
        self._bubble.show_bubble(text=text)
        self._mode = "bubble"

    def _dismiss(self) -> None:
        if self._mode == "main":
            # Esc из full → назад в bubble с текущим текстом
            self._switch_to_bubble()
            return
        if self._mode == "bubble":
            self._bubble.hide_bubble()
        self._mode = "hidden"

    def _auto_hide(self) -> None:
        if self._mode == "bubble" and not self._bubble.isActiveWindow():
            self._bubble.hide_bubble()
        elif self._mode == "main" and not self._main_win.isActiveWindow():
            self._main_win.hide_main()

    def _on_text_replaced(self, text: str) -> None:
        logger.info("Text replaced in clipboard (%d chars)", len(text))

    def _ensure_api_key(self) -> bool:
        """Yandex AI Studio: одно окно — API Key + Folder ID."""
        cfg = self._config
        llm = cfg.llm

        if llm.provider == "ollama":
            return True

        ready = (
            llm.provider == "yandex"
            and bool(llm.api_key.strip())
            and bool(llm.folder_id.strip())
        )
        if ready:
            logger.info(
                "API ready (provider=%s, folder=%s, model=%s)",
                llm.provider,
                llm.folder_id,
                llm.model,
            )
            return True

        dlg = QDialog()
        dlg.setWindowTitle("GrammarFlow — Yandex AI Studio")
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(
            "QDialog { background: #f8fafc; color: #0f172a; }"
            "QLabel { color: #0f172a; background: transparent; }"
            "QLineEdit {"
            "  background: #ffffff; color: #0f172a;"
            "  border: 1px solid #94a3b8; border-radius: 6px; padding: 6px;"
            "}"
            "QPushButton { color: #0f172a; padding: 6px 14px; }"
        )

        layout = QVBoxLayout(dlg)
        hint = QLabel(
            "Вставьте данные из Yandex Cloud / AI Studio.\n"
            "Оба поля обязательны. Секреты сохраняются в .env проекта\n"
            f"({ENV_FILE}), не в config.json."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #0f172a; font-size: 13px;")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        key_edit = QLineEdit()
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_edit.setPlaceholderText("секретный ключ сервисного аккаунта")
        key_edit.setText(llm.api_key if llm.provider == "yandex" else "")
        key_lbl = QLabel(
            "<b>API Key</b><br>"
            "<span style='color:#334155;font-size:12px'>"
            "Ключ доступа к модели (создаётся у сервисного аккаунта в Yandex Cloud)"
            "</span>"
        )
        key_lbl.setTextFormat(Qt.TextFormat.RichText)
        key_lbl.setWordWrap(True)
        key_lbl.setStyleSheet("color: #0f172a;")
        form.addRow(key_lbl, key_edit)

        folder_edit = QLineEdit()
        folder_edit.setPlaceholderText("например b1g…")
        folder_edit.setText(llm.folder_id or "")
        folder_lbl = QLabel(
            "<b>Folder ID</b><br>"
            "<span style='color:#334155;font-size:12px'>"
            "ID каталога в облаке — входит в адрес модели gpt://&lt;folder&gt;/…"
            "</span>"
        )
        folder_lbl.setTextFormat(Qt.TextFormat.RichText)
        folder_lbl.setWordWrap(True)
        folder_lbl.setStyleSheet("color: #0f172a;")
        form.addRow(folder_lbl, folder_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        key_edit.setFocus()
        dlg.raise_()
        dlg.activateWindow()

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False

        key = key_edit.text().strip()
        folder = folder_edit.text().strip()
        if not key or not folder:
            QMessageBox.warning(
                None,
                "GrammarFlow",
                "Нужны оба поля: API Key и Folder ID.",
            )
            return False

        save_secrets_to_env(key, folder)
        llm.api_key = key
        llm.folder_id = folder
        llm.provider = "yandex"
        llm.base_url = "https://ai.api.cloud.yandex.net/v1"
        llm.model = "yandexgpt-5-lite"
        cfg.save()
        logger.info(
            "Saved Yandex credentials to %s (folder=%s)",
            ENV_FILE,
            llm.folder_id,
        )
        return True

    def run(self) -> int:
        logger.info("GrammarFlow starting...")
        if not self._ensure_api_key():
            QMessageBox.warning(
                None,
                "GrammarFlow",
                "Без API-ключа и Folder ID приложение не сможет работать.",
            )
            return 0

        self._hotkeys.start()

        def _on_sigint(*_args):
            self._quit_app()

        try:
            signal.signal(signal.SIGINT, _on_sigint)
            signal.signal(signal.SIGTERM, _on_sigint)
        except (ValueError, OSError):
            pass

        ping = QTimer()
        ping.start(400)
        ping.timeout.connect(lambda: None)

        logger.info(
            "Alt+C refresh | Esc dismiss/back | local: Ctrl+Enter / Ctrl+Shift+Enter / Ctrl+R | %s / %s",
            self._config.llm.provider,
            self._config.llm.model,
        )

        try:
            code = self._app.exec()
        except KeyboardInterrupt:
            code = 0
        finally:
            self._hotkeys.stop()
            self._tray.hide()
        return code


if __name__ == "__main__":
    try:
        # QApplication нужен до диалогов; lock — до второго hotkey-listener
        _boot = QApplication.instance() or QApplication(sys.argv)
        _lock = _acquire_single_instance()
        if _lock is None:
            QMessageBox.information(
                None,
                "GrammarFlow",
                "GrammarFlow уже запущен.\n"
                "Закройте старый экземпляр из трея (Выход) или снимите процесс.",
            )
            sys.exit(0)
        app = GrammarFlowApp()
        app._instance_lock = _lock  # keep alive until process exit
        sys.exit(app.run())
    except KeyboardInterrupt:
        sys.exit(0)
