"""Shared API constants — languages, providers, upload settings."""

import os
from typing import Any

# ── Uploads ──────────────────────────────────────────────────────────
# UPLOADS_DIR is the folder that holds avatar files (one nested level
# below the mount point, so the public URL stays ``/uploads/avatars/…``).
# The folder itself is resolved from ``Settings.effective_upload_dir``
# so the ``UPLOAD_DIR`` env var (see .env.example) controls where
# avatars live in every environment. Relative values resolve against
# ``ROLEPLAY_DATA_DIR`` when set, otherwise against the project root.
from app.infrastructure.config import Settings


def _resolve_uploads_dir() -> str:
    return str(Settings.from_env().effective_upload_dir / "avatars")


UPLOADS_DIR = _resolve_uploads_dir()

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


# ── Languages ────────────────────────────────────────────────────────

LANGUAGES: list[dict[str, str]] = [
    {"id": "en", "label": "English"},
    {"id": "ru", "label": "Русский"},
    {"id": "de", "label": "Deutsch"},
    {"id": "fr", "label": "Français"},
    {"id": "ja", "label": "日本語"},
    {"id": "zh", "label": "中文"},
    {"id": "ko", "label": "한국어"},
]


# ── LLM Providers ────────────────────────────────────────────────────

PROVIDERS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "label": "OpenRouter",
        "default_base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "needs_key": True,
        "manual_setup": False,
        "description": "Access many models through one API",
    },
    "openai": {
        "label": "OpenAI",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "needs_key": True,
        "manual_setup": False,
        "description": "Official OpenAI API",
    },
    "lm-studio": {
        "label": "LM Studio",
        "default_base_url": "http://localhost:1234/v1",
        "default_model": "",
        "needs_key": False,
        "manual_setup": False,
        "description": "Local models via LM Studio",
    },
    "deepseek": {
        "label": "DeepSeek",
        "default_base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "needs_key": True,
        "manual_setup": False,
        "description": "DeepSeek chat & reasoning models",
    },
    "gigachat": {
        "label": "GigaChat",
        "default_base_url": "https://gigachat.devices.sberbank.ru/api/v1",
        "default_model": "GigaChat",
        "needs_key": True,
        "manual_setup": True,
        "description": "Sberbank GigaChat (OAuth required)",
    },
    "grok": {
        "label": "Grok (x.AI)",
        "default_base_url": "https://api.x.ai/v1",
        "default_model": "grok-2-latest",
        "needs_key": True,
        "manual_setup": False,
        "description": "x.AI Grok models",
    },
    "kimi": {
        "label": "Kimi (Moonshot)",
        "default_base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "needs_key": True,
        "manual_setup": False,
        "description": "Moonshot AI Kimi models",
    },
    "minimax": {
        "label": "MiniMax",
        "default_base_url": "https://api.minimaxi.com/v1",
        "default_model": "MiniMax-Text-01",
        "needs_key": True,
        "manual_setup": False,
        "description": "MiniMax chat & vision models",
    },
    "yandexgpt": {
        "label": "YandexGPT",
        "default_base_url": "https://llm.api.cloud.yandex.net/foundationModels/v1",
        "default_model": "yandexgpt/latest",
        "needs_key": True,
        "manual_setup": True,
        "description": "Yandex Cloud YandexGPT (IAM token required)",
    },
    "z-ai": {
        "label": "Z.AI (GLM)",
        "default_base_url": "https://api.z.ai/v1",
        "default_model": "glm-4.6",
        "needs_key": True,
        "manual_setup": False,
        "description": "Zhipu AI GLM models",
    },
    "custom": {
        "label": "Custom",
        "default_base_url": "",
        "default_model": "",
        "needs_key": False,
        "manual_setup": False,
        "description": "Any OpenAI-compatible API",
    },
}
