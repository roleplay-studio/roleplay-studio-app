"""Unit tests for ``SettingsService`` (bot category CRUD)."""

from __future__ import annotations

import pytest

from app.application.exceptions import ValidationError
from app.application.services.settings import (
    SettingsService,
    default_seed_categories,
)


class FakeRepository:
    """In-memory replacement for ``SettingsRepository``.

    Mirrors ``SqlAlchemySettingsRepository`` just enough for unit
    tests; no DB fixture needed.
    """

    def __init__(self, seed: list[str] | None = None) -> None:
        self._payload: str | None = None
        if seed is not None:
            import json

            self._payload = json.dumps(seed, ensure_ascii=False)

    async def get_bot_categories(self) -> list[str] | None:
        if self._payload is None:
            return None
        import json

        return json.loads(self._payload)

    async def set_bot_categories(
        self, categories: list[str], payload: str
    ) -> None:
        del categories
        self._payload = payload

    @property
    def last_payload(self) -> str | None:
        return self._payload


# ── Seed behaviour ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_seeds_from_default_when_empty():
    """No row in the repo → service should fall back to defaults."""
    repo = FakeRepository()
    svc = SettingsService(repo)
    out = await svc.list_bot_categories()
    assert out == default_seed_categories()
    # The seed MUST be persisted so the next read doesn't repeat
    # the fallback (and so the front-end doesn't see a phantom row).
    assert repo.last_payload is not None
    import json

    assert json.loads(repo.last_payload) == default_seed_categories()


@pytest.mark.asyncio
async def test_list_returns_persisted_value_when_present():
    stored = ["X", "Y", "Z"]
    repo = FakeRepository(seed=stored)
    svc = SettingsService(repo)
    assert await svc.list_bot_categories() == stored


# ── add_category ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_appends_unique_name():
    repo = FakeRepository(seed=["Anime"])
    svc = SettingsService(repo)
    out = await svc.add_category("Romance")
    assert out == ["Anime", "Romance"]


@pytest.mark.asyncio
async def test_add_is_idempotent_case_insensitive():
    repo = FakeRepository(seed=["Anime"])
    svc = SettingsService(repo)
    out = await svc.add_category("anime")
    assert out == ["Anime"]


@pytest.mark.asyncio
async def test_add_rejects_empty():
    repo = FakeRepository(seed=["Anime"])
    svc = SettingsService(repo)
    with pytest.raises(ValidationError):
        await svc.add_category("   ")


@pytest.mark.asyncio
async def test_add_strips_whitespace():
    repo = FakeRepository(seed=[])
    svc = SettingsService(repo)
    out = await svc.add_category("  Sci-Fi  ")
    assert out == ["Sci-Fi"]


# ── rename_category ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rename_preserves_order():
    repo = FakeRepository(seed=["Anime", "Game", "Fantasy"])
    svc = SettingsService(repo)
    out = await svc.rename_category("Game", "VideoGame")
    assert out == ["Anime", "VideoGame", "Fantasy"]


@pytest.mark.asyncio
async def test_rename_unknown_raises():
    repo = FakeRepository(seed=["Anime"])
    svc = SettingsService(repo)
    with pytest.raises(ValidationError):
        await svc.rename_category("Nope", "Anything")


@pytest.mark.asyncio
async def test_rename_to_existing_other_raises():
    repo = FakeRepository(seed=["Anime", "Game"])
    svc = SettingsService(repo)
    with pytest.raises(ValidationError):
        await svc.rename_category("Game", "Anime")


@pytest.mark.asyncio
async def test_rename_same_case_is_noop():
    """Renaming to the same name (modulo case) must persist nothing
    so downstream audit logs don't lie."""
    repo = FakeRepository(seed=["Anime"])
    svc = SettingsService(repo)
    out = await svc.rename_category("Anime", "anime")
    assert out == ["Anime"]


# ── delete_category ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_removes_entry():
    repo = FakeRepository(seed=["Anime", "Game"])
    svc = SettingsService(repo)
    out = await svc.delete_category("Anime")
    assert out == ["Game"]


@pytest.mark.asyncio
async def test_delete_unknown_raises():
    repo = FakeRepository(seed=["Anime"])
    svc = SettingsService(repo)
    with pytest.raises(ValidationError):
        await svc.delete_category("Nope")


# ── replace_all ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_replace_all_strips_and_dedupes():
    repo = FakeRepository(seed=["Anime", "Game", "Adventure"])
    svc = SettingsService(repo)
    out = await svc.replace_all(["Anime", "  Anime  ", "Game"])
    # Whitespace stripped, duplicates dropped, order preserved by
    # first occurrence — same contract as ``filter_valid``.
    assert out == ["Anime", "Game"]


@pytest.mark.asyncio
async def test_replace_all_silently_dedupes():
    """Case-insensitive dedup, first wins — same as filter_valid."""
    repo = FakeRepository(seed=[])
    svc = SettingsService(repo)
    out = await svc.replace_all(["Anime", "anime", "ANIME", "Game"])
    assert out == ["Anime", "Game"]


@pytest.mark.asyncio
async def test_replace_all_rejects_blank_entry():
    """A blank between two valid entries rejects the whole op so the
    client can't silently nuke the first two via a typo in the third."""
    repo = FakeRepository(seed=[])
    svc = SettingsService(repo)
    with pytest.raises(ValidationError):
        await svc.replace_all(["Anime", "   ", "Game"])


# ── filter_valid ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_filter_valid_drops_unknown_and_dedupes():
    repo = FakeRepository(seed=["Anime", "Game"])
    svc = SettingsService(repo)
    out = await svc.filter_valid(["Anime", "Anime", "Nope", "Game"])
    assert out == ["Anime", "Game"]


@pytest.mark.asyncio
async def test_filter_valid_strips_whitespace_and_drops_blank():
    repo = FakeRepository(seed=["Anime"])
    svc = SettingsService(repo)
    out = await svc.filter_valid(["  Anime  ", "", "   "])
    assert out == ["Anime"]


@pytest.mark.asyncio
async def test_categories_invalid_for_returns_only_unknown():
    repo = FakeRepository(seed=["Anime"])
    svc = SettingsService(repo)
    out = await svc.categories_invalid_for(["Anime", "Ghost", "Game"])
    assert out == ["Ghost", "Game"]


@pytest.mark.asyncio
async def test_categories_invalid_for_empty_input():
    repo = FakeRepository(seed=["Anime"])
    svc = SettingsService(repo)
    assert await svc.categories_invalid_for([]) == []
    assert await svc.categories_invalid_for(None) == []
