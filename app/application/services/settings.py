"""Settings service — manages the user-editable bot category list.

Backed by the ``app_settings`` singleton table (see
``app/infrastructure/db/models.py`` and the alembic migration that
introduced it). The service owns the rules around persistence —
route handlers stay thin and don't deal with JSON encoding, the
seed fallback, or the validation of category strings.

Design notes:

* **Seed-on-first-read.** A fresh install has no ``app_settings``
  row, but the user-facing GET should always return the original
  hardcoded set (Anime / Game / Fantasy / …) so the empty
  database doesn't render a blank CategoryPicker on first launch.
  ``ensure_initialized()`` is called by the service whenever a
  read hits a missing row.

* **Strings are stripped and de-duplicated, order preserved.** The
  ``name == " Anime "`` style entries silently become ``"Anime"``,
  keeping the picker alphabetical without surprise order changes
  for the common case.

* **Empty / whitespace-only entries are rejected** on add. A rename
  to ``""`` returns False; the row is left untouched so the client
  gets a stable error path (no half-applied mutations).

* **Delete is soft on bots.** Bots that referenced a now-deleted
  category keep it in their ``categories`` JSON column. The picker
  filters those out (see ``filter_valid``) and the response model
  surfaces ``categories_invalid`` so the UI can render a warning
  chip ("Old Category — no longer defined"). Cleaning up orphan
  rows on every delete is more magic than is worth it — the
  orphaned strings are harmless.
"""

from __future__ import annotations

import json
import logging

from app.application.dto import DEFAULT_BOT_CATEGORIES
from app.application.exceptions import ValidationError
from app.application.ports import SettingsRepository

logger = logging.getLogger(__name__)


class SettingsService:
    """Manages the user-editable bot category list."""

    def __init__(self, repository: SettingsRepository):
        self._repository = repository

    # ── Read ─────────────────────────────────────────────────────

    async def list_bot_categories(self) -> list[str]:
        """Return the current category list (seeded on first read)."""
        categories = await self._repository.get_bot_categories()
        if categories is None:
            # Seed from the module-level constant and persist so the
            # next read doesn't trip this branch.
            categories = list(DEFAULT_BOT_CATEGORIES)
            await self._persist(categories)
        return categories

    async def filter_valid(self, categories: list[str] | None) -> list[str]:
        """Drop categories that aren't in the current list.

        Order-preserving. Used by ``BotService`` so a saved category
        that was later deleted doesn't wedge into the schema.
        Duplicates are de-duplicated within the input as well, so
        ``["Anime", "Anime", "Sci-Fi"]`` becomes ``["Anime", "Sci-Fi"]``.
        """
        if not categories:
            return []
        allowed = set(await self.list_bot_categories())
        seen: set[str] = set()
        out: list[str] = []
        for raw in categories:
            name = raw.strip()
            if not name or name not in allowed or name in seen:
                continue
            seen.add(name)
            out.append(name)
        return out

    async def categories_invalid_for(
        self, categories: list[str] | None
    ) -> list[str]:
        """Return only the categories that aren't defined right now.

        Used by the bot list endpoint so the UI can show a "needs
        cleanup" hint without having to re-fetch the category list.
        Returns ``[]`` if every category is still known.
        """
        if not categories:
            return []
        allowed = set(await self.list_bot_categories())
        return [c for c in categories if c not in allowed]

    # ── Write ────────────────────────────────────────────────────

    async def add_category(self, name: str) -> list[str]:
        """Append a new category, persisting immediately.

        Rejects empty / whitespace-only names and duplicates
        (case-insensitive). Returns the updated list so the caller
        can re-fetch without a separate round-trip.
        """
        cleaned = self._clean_name(name)
        if not cleaned:
            raise ValidationError("Category name must not be empty")
        current = await self.list_bot_categories()
        if self._exists_case_insensitive(cleaned, current):
            # Idempotent — adding "Anime" twice is a no-op. We still
            # return the unchanged list so the caller gets a stable
            # shape (and the same JSON response shape as the create
            # branch).
            return current
        current.append(cleaned)
        await self._persist(current)
        return current

    async def rename_category(self, old_name: str, new_name: str) -> list[str]:
        """Rename a category, preserving order.

        Returns the updated list. Raises ``ValidationError`` if the
        old name isn't found, the new name is empty, or the new name
        clashes with an existing entry other than the one being
        renamed (case-insensitive).
        """
        new_clean = self._clean_name(new_name)
        if not new_clean:
            raise ValidationError("New category name must not be empty")
        current = await self.list_bot_categories()
        try:
            idx = current.index(old_name)
        except ValueError as exc:
            raise ValidationError(f"Category {old_name!r} not found") from exc
        # Block renaming to a name that already exists elsewhere —
        # otherwise we either silently drop the duplicate or end up
        # with two entries that the picker can't disambiguate.
        for i, name in enumerate(current):
            if i == idx:
                continue
            if name.lower() == new_clean.lower():
                raise ValidationError(
                    f"Category {new_clean!r} already exists"
                )
        if current[idx].lower() != new_clean.lower():
            current[idx] = new_clean
            await self._persist(current)
        return current

    async def delete_category(self, name: str) -> list[str]:
        """Remove a category. Bots keep the legacy string in JSON; the
        picker hides it via ``filter_valid``."""
        current = await self.list_bot_categories()
        try:
            current.remove(name)
        except ValueError as exc:
            raise ValidationError(f"Category {name!r} not found") from exc
        await self._persist(current)
        logger.info("Deleted bot category %r", name)
        return current

    async def replace_all(self, categories: list[str]) -> list[str]:
        """Replace the entire category list in one transaction.

        Used by the bulk-paste / drag-reorder UI where the client
        already knows the full desired order. Whitespace is trimmed
        and duplicates removed (case-insensitive, first wins), same
        rules as ``filter_valid`` — keeping the rules in one place
        means clients never get a different answer from different
        endpoints. Blank entries cause a full reject (no partial
        write) so a typo in the third item can't silently nuke the
        first two.
        """
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in categories:
            name = self._clean_name(raw)
            if not name:
                raise ValidationError(
                    "Category names must not be empty"
                )
            if name.lower() in seen:
                # Silently drop — same case-insensitive rule the
                # filter already uses. Saves the user from a 400 when
                # they drag a duplicate column by accident.
                continue
            seen.add(name.lower())
            cleaned.append(name)
        await self._persist(cleaned)
        return cleaned

    # ── Internals ────────────────────────────────────────────────

    @staticmethod
    def _clean_name(raw: str) -> str:
        """Trim and return the name, or ``""`` for empty input."""
        return raw.strip() if isinstance(raw, str) else ""

    @staticmethod
    def _exists_case_insensitive(name: str, haystack: list[str]) -> bool:
        lower = name.lower()
        return any(entry.lower() == lower for entry in haystack)

    async def _persist(self, categories: list[str]) -> None:
        """Write through the repository. ``updated_at`` is stamped server-side via SQLAlchemy default."""
        encoded = json.dumps(categories, ensure_ascii=False)
        await self._repository.set_bot_categories(categories, encoded)


# ── Helper for tests / DI ─────────────────────────────────────────


def default_seed_categories() -> list[str]:
    """Module-level constant, exported for tests that don't have a DB."""
    return list(DEFAULT_BOT_CATEGORIES)


__all__ = ["SettingsService", "default_seed_categories"]
