"""
GrammarFlow — Менеджер глобальных горячих клавиш.

Кастомный Listener: на Windows при Alt буква часто приходит без
нормального char (только vk). GlobalHotKeys из-за этого не ловит Alt+C.
"""

from __future__ import annotations

import logging
from typing import Optional

from pynput import keyboard
from PySide6.QtCore import QObject, Signal

from config import HotkeyConfig

logger = logging.getLogger(__name__)

_MODIFIER_ALIASES = {
    "alt": "alt",
    "alt_l": "alt",
    "alt_r": "alt",
    "alt_gr": "alt",
    "ctrl": "ctrl",
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "control": "ctrl",
    "control_l": "ctrl",
    "control_r": "ctrl",
    "shift": "shift",
    "shift_l": "shift",
    "shift_r": "shift",
}

_VK_LETTERS = {code: chr(code).lower() for code in range(65, 91)}  # A–Z
_VK_SPECIAL = {
    13: "enter",
    27: "escape",
    32: "space",
    9: "tab",
}


def _parse_hotkey(hotkey_str: str) -> tuple[frozenset[str], str]:
    parts = [p.strip().lower() for p in hotkey_str.split("+") if p.strip()]
    key = parts[-1]
    if key in ("esc",):
        key = "escape"
    if key in ("return",):
        key = "enter"
    if key in ("control",):
        key = "ctrl"
    modifiers = frozenset(_MODIFIER_ALIASES.get(p, p) for p in parts[:-1])
    return modifiers, key


def _key_to_name(key) -> str:
    """Нормализовать нажатую клавишу в каноническое имя."""
    name = getattr(key, "name", None)
    if name:
        name = name.lower()
        if name in _MODIFIER_ALIASES:
            return _MODIFIER_ALIASES[name]
        if name in ("esc", "escape"):
            return "escape"
        if name in ("enter", "return"):
            return "enter"
        return name

    vk = getattr(key, "vk", None)
    if vk is not None:
        if vk in _VK_LETTERS:
            return _VK_LETTERS[vk]
        if vk in _VK_SPECIAL:
            return _VK_SPECIAL[vk]

    char = getattr(key, "char", None)
    if isinstance(char, str) and len(char) == 1 and char.isascii() and char.isalpha():
        return char.lower()

    return ""


class HotkeyManager(QObject):
    """Глобальный перехватчик горячих клавиш."""

    toggle_bubble_triggered = Signal()
    auto_correct_triggered = Signal()
    suggest_improve_triggered = Signal()
    dismiss_triggered = Signal()

    def __init__(self, config: HotkeyConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._listener: Optional[keyboard.Listener] = None
        self._current_modifiers: set[str] = set()

        # Глобально только Alt+C и Esc — correct/improve живут как локальные QShortcut,
        # чтобы не перехватывать Ctrl+Enter в Outlook и других приложениях.
        self._hotkey_map: dict[tuple[frozenset[str], str], Signal] = {
            _parse_hotkey(config.toggle_bubble): self.toggle_bubble_triggered,
            _parse_hotkey(config.dismiss): self.dismiss_triggered,
        }

    def start(self) -> None:
        if self._listener is not None:
            logger.warning("Hotkey listener already running")
            return

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        combos = [
            "+".join([*sorted(mods), key]) if mods else key
            for mods, key in self._hotkey_map
        ]
        logger.info("Global hotkey listener started: %s", ", ".join(combos))

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
            logger.info("Global hotkey listener stopped")

    def _on_press(self, key) -> None:
        name = _key_to_name(key)
        if not name:
            return

        if name in ("alt", "ctrl", "shift"):
            self._current_modifiers.add(name)
            return

        mods = frozenset(self._current_modifiers)
        signal = self._hotkey_map.get((mods, name))
        if signal is not None:
            combo = "+".join([*sorted(mods), name]) if mods else name
            logger.info("Hotkey triggered: %s", combo)
            signal.emit()

    def _on_release(self, key) -> None:
        name = _key_to_name(key)
        if name in ("alt", "ctrl", "shift"):
            self._current_modifiers.discard(name)
