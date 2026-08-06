"""
GrammarFlow — Конфигурация приложения.
Несекретные параметры — в ~/.grammarflow/config.json.
Секреты (API key, folder_id) — только в .env рядом с этим файлом.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


CONFIG_DIR = Path.home() / ".grammarflow"
CONFIG_FILE = CONFIG_DIR / "config.json"
ENV_FILE = Path(__file__).resolve().parent / ".env"

_SECRET_FIELDS = frozenset({"api_key", "folder_id"})


def save_secrets_to_env(api_key: str, folder_id: str) -> None:
    """Создать/обновить .env, сохранив прочие строки."""
    updates = {
        "YANDEX_API_KEY": api_key.strip(),
        "YANDEX_FOLDER_ID": folder_id.strip(),
    }
    lines: list[str] = []
    seen: set[str] = set()

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
            if m and m.group(1) in updates:
                key = m.group(1)
                lines.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                lines.append(line)

    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.environ["YANDEX_API_KEY"] = updates["YANDEX_API_KEY"]
    os.environ["YANDEX_FOLDER_ID"] = updates["YANDEX_FOLDER_ID"]


def _env_has_secret(name: str) -> bool:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            m = re.match(rf"^{re.escape(name)}\s*=\s*(.*)$", line)
            if m and m.group(1).strip().strip("\"'"):
                return True
    return bool(os.environ.get(name, "").strip())


@dataclass
class LLMConfig:
    """Настройки подключения к LLM-провайдеру."""
    provider: Literal["yandex", "openrouter", "openai", "gemini", "ollama"] = "yandex"
    api_key: str = ""
    base_url: str = "https://ai.api.cloud.yandex.net/v1"
    folder_id: str = ""
    model: str = "yandexgpt-5-lite"
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout: int = 45
    # OpenRouter-specific (если вручную вернуть provider=openrouter)
    app_title: str = "GrammarFlow"
    http_referer: str = "https://github.com/grammarflow"
    # Retry settings
    max_retries: int = 2
    retry_delay_s: float = 1.0

    def __post_init__(self):
        """Подхватить ключ / folder_id из окружения если не заданы."""
        if not self.api_key:
            self.api_key = (
                os.environ.get("YANDEX_API_KEY", "")
                or os.environ.get("YC_API_KEY", "")
                or os.environ.get("OPENROUTER_API_KEY", "")
                or os.environ.get("OPENAI_API_KEY", "")
            )
        if not self.folder_id:
            self.folder_id = (
                os.environ.get("YANDEX_FOLDER_ID", "")
                or os.environ.get("YC_FOLDER_ID", "")
            )


# ======================================================================
# Каталог бесплатных моделей OpenRouter
# ======================================================================
OPENROUTER_FREE_MODELS = {
    # ---- Лучшее качество (рекомендуемые) ----
    "google/gemma-4-26b-a4b-it:free": {
        "label": "Gemma 4 26B (free)",
        "description": "Актуальная Gemma 4, хорошо с русским",
        "max_context": 131072,
        "recommended": True,
    },
    "google/gemma-4-31b-it:free": {
        "label": "Gemma 4 31B (free)",
        "description": "Крупнее Gemma 4, выше качество",
        "max_context": 131072,
        "recommended": True,
    },
    "openai/gpt-oss-20b:free": {
        "label": "GPT-OSS 20B (free)",
        "description": "Open-weight модель OpenAI, универсальная",
        "max_context": 131072,
        "recommended": True,
    },
    # ---- Быстрые / лёгкие ----
    "nvidia/nemotron-nano-9b-v2:free": {
        "label": "Nemotron Nano 9B (free)",
        "description": "Быстрая модель NVIDIA для коротких правок",
        "max_context": 131072,
        "recommended": False,
    },
    "inclusionai/ling-3.0-flash:free": {
        "label": "Ling 3.0 Flash (free)",
        "description": "Лёгкая flash-модель",
        "max_context": 131072,
        "recommended": False,
    },
    "nvidia/nemotron-nano-12b-v2-vl:free": {
        "label": "Nemotron Nano 12B VL (free)",
        "description": "Мультимодальная Nano от NVIDIA",
        "max_context": 131072,
        "recommended": False,
    },
    # ---- Запасные ----
    "poolside/laguna-s-2.1:free": {
        "label": "Laguna S 2.1 (free)",
        "description": "Запасная free-модель",
        "max_context": 32768,
        "recommended": False,
    },
}


@dataclass
class HotkeyConfig:
    """Глобальные хоткеи (остальное — локальные QShortcut в окнах)."""
    toggle_bubble: str = "alt+c"
    dismiss: str = "escape"
    # Документация локальных шорткатов (не регистрируются глобально):
    # auto_correct: Ctrl+Enter — в bubble/full
    # suggest_improve: Ctrl+Shift+Enter — в bubble/full
    # refresh_clipboard: Ctrl+R — в bubble/full
    auto_correct: str = "ctrl+enter"
    suggest_improve: str = "ctrl+shift+enter"
    refresh_clipboard: str = "ctrl+r"


@dataclass
class UIConfig:
    """Параметры интерфейса."""
    bubble_width: int = 420
    bubble_max_height: int = 580
    main_width: int = 560
    main_height: int = 680
    border_radius: int = 12
    animation_duration_ms: int = 200
    preview_max_chars: int = 500
    mica_enabled: bool = True
    acrylic_fallback: bool = True
    language: str = "ru"
    preferred_free_model: str = "google/gemma-4-26b-a4b-it:free"


@dataclass
class AppConfig:
    """Корневая конфигурация приложения."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    start_with_system: bool = False
    minimize_to_tray: bool = True

    @classmethod
    def load(cls) -> "AppConfig":
        """Загрузить конфиг: .env для секретов, JSON для остального."""
        load_dotenv(ENV_FILE)

        if not CONFIG_FILE.exists():
            return cls()

        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
            llm_raw = dict(raw.get("llm", {}) or {})

            # Миграция: секреты из старого JSON → .env
            legacy_key = str(llm_raw.get("api_key") or "").strip()
            legacy_folder = str(llm_raw.get("folder_id") or "").strip()
            need_migrate = False
            if legacy_key and not _env_has_secret("YANDEX_API_KEY"):
                need_migrate = True
            if legacy_folder and not _env_has_secret("YANDEX_FOLDER_ID"):
                need_migrate = True
            if need_migrate and (legacy_key or legacy_folder):
                save_secrets_to_env(
                    legacy_key or os.environ.get("YANDEX_API_KEY", ""),
                    legacy_folder or os.environ.get("YANDEX_FOLDER_ID", ""),
                )
                load_dotenv(ENV_FILE, override=True)

            # Секреты только из окружения, не из JSON
            for secret in _SECRET_FIELDS:
                llm_raw.pop(secret, None)

            known = {f.name for f in fields(LLMConfig)}
            llm_raw = {k: v for k, v in llm_raw.items() if k in known}
            cfg = cls(
                llm=LLMConfig(**llm_raw),
                hotkeys=HotkeyConfig(**{
                    k: v for k, v in (raw.get("hotkeys") or {}).items()
                    if k in {f.name for f in fields(HotkeyConfig)}
                }),
                ui=UIConfig(**{
                    k: v for k, v in (raw.get("ui") or {}).items()
                    if k in {f.name for f in fields(UIConfig)}
                }),
                start_with_system=raw.get("start_with_system", False),
                minimize_to_tray=raw.get("minimize_to_tray", True),
            )
            # Вычистить секреты из JSON, если они ещё там
            if legacy_key or legacy_folder:
                cfg.save()
            return cfg
        except (json.JSONDecodeError, TypeError):
            return cls()

    def save(self) -> None:
        """Сохранить несекретный конфиг в JSON (без api_key / folder_id)."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        llm = data.get("llm") or {}
        llm["api_key"] = ""
        llm["folder_id"] = ""
        data["llm"] = llm
        CONFIG_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
