"""Pytest configuration and fixtures for testing."""

import base64
import json
import os
import sys
import zlib
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock langgraph and langchain before any app imports
sys.modules["langgraph"] = MagicMock()
sys.modules["langgraph.graph"] = MagicMock()
sys.modules["langchain_openai"] = MagicMock()
sys.modules["langchain_core"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["langchain_community"] = MagicMock()
sys.modules["langchain_chroma"] = MagicMock()


def _build_v2_card_png(card_data: dict) -> bytes:
    """Build a PNG with V2 character card embedded in 'chara' tEXt chunk."""
    payload = {"spec": "chara-card-v2", "spec_version": "2.0", "data": card_data}
    img = Image.new("RGB", (64, 64), color=(100, 150, 200))
    meta = PngInfo()
    raw = json.dumps(payload).encode("utf-8")
    encoded = base64.b64encode(zlib.compress(raw)).decode("ascii")
    meta.add_text("chara", encoded)
    buf = BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()


@pytest.fixture
def sample_v2_png_bytes() -> bytes:
    """A V2 character card PNG built in-memory — ready for multipart upload tests."""
    card_data = {
        "name": "Luna the Dream Weaver",
        "description": "A mystical weaver of dreams.",
        "personality": "Gentle, wise, ethereal.",
        "scenario": "A moonlit garden.",
        "first_mes": "Welcome, traveler.",
        "alternate_greetings": ["alt1", "alt2"],
        "system_prompt": "Speak verse.",
        "post_history_instructions": "End with ?",
        "tags": ["Fantasy", "Mystic"],
        "character_book": {"entries": [{"content": "lore entry one"}]},
    }
    return _build_v2_card_png(card_data)


@pytest.fixture
def sample_bot_json() -> bytes:
    """A portable bot JSON file matching the ImportBotRequest shape."""
    return json.dumps(
        {
            "name": "Sample Bot",
            "personality": "Friendly and helpful",
            "first_message": "Hi there!",
            "scenario": "A coffee shop",
            "description": "A friendly barista",
            "categories": ["Slice of Life"],
            "bot_type": "rp",
            "knowledge": [],
        }
    ).encode("utf-8")
