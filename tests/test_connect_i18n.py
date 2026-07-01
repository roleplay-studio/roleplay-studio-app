"""Tests for Tauri Android wrapper — i18n keys and util functions."""

# Import i18n via a tiny helper that pulls the keys we care about.
# i18n.ts is TypeScript, but we only need the keys list to verify
# both en and ru provide the same set of `connect.*` keys.
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "frontend" / "src" / "lib" / "i18n.ts"


def _extract_keys(text: str, lang_marker: str) -> set[str]:
    """Pull `connect.*` keys out of a lang block in i18n.ts.

    The i18n.ts file uses the form `en: Object.freeze({ ... }),` so we
    anchor on the `Object.freeze({` opener and capture until the
    matching closing `}),` (greedy across newlines). A trailing comma
    is allowed (each lang block except the last has one).
    """
    pattern = rf"{lang_marker}\s*Object\.freeze\(\{{(.*?)\n  \}}\),"
    m = re.search(pattern, text, re.DOTALL)
    assert m, f"Lang block '{lang_marker}' not found"
    block = m.group(1)
    # Match `'connect.XXX':` patterns (key only; value ignored)
    keys = set(re.findall(r"'(connect\.[a-zA-Z_]+)':", block))
    return keys


@pytest.fixture(scope="module")
def en_keys() -> set[str]:
    text = I18N.read_text()
    return _extract_keys(text, "en:")


@pytest.fixture(scope="module")
def ru_keys() -> set[str]:
    text = I18N.read_text()
    return _extract_keys(text, "ru:")


def test_connect_keys_en_nonempty(en_keys: set[str]) -> None:
    """English must declare at least the core connect.* keys."""
    required = {
        "connect.title",
        "connect.url_label",
        "connect.url_placeholder",
        "connect.test_connection",
        "connect.save",
    }
    missing = required - en_keys
    assert not missing, f"Missing en keys: {missing}"


def test_connect_keys_en_ru_parity(en_keys: set[str], ru_keys: set[str]) -> None:
    """All Russian connect.* keys must have an English counterpart."""
    only_ru = ru_keys - en_keys
    only_en = en_keys - ru_keys
    assert not only_ru, f"ru keys without en: {only_ru}"
    assert not only_en, f"en keys without ru: {only_en}"


def test_connect_keys_minimum_count(en_keys: set[str], ru_keys: set[str]) -> None:
    """Sanity: each lang has at least 10 connect.* keys (smoke test
    that the spec's 17 keys were actually added)."""
    assert len(en_keys) >= 10
    assert len(ru_keys) >= 10
