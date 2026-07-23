"""Service layer for bot versioning.

Captures full snapshots of a ``Bot`` into ``BotVersion`` rows, lists
them, and restores the bot from a snapshot. Restoring auto-saves the
live state first so a user can always undo a restore.

Snapshot shape (JSON):

    {
        "name": str,
        "description": str,
        "personality": str,
        "first_message": str,
        "scenario": str,
        "avatar_path": str | None,
        "categories": list[str],
        "bot_type": str,
        "alternate_greetings": list[str],
        "mes_example": str
    }
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from app.application.dto import BotVersionDTO
from app.application.exceptions import NotFoundError
from app.application.ports import BotRepository, BotVersionRepository

if TYPE_CHECKING:
    from app.infrastructure.db.models import Bot, BotVersion
else:
    from app.infrastructure.db.models import BotVersion

logger = logging.getLogger(__name__)


def serialize_bot(bot: Bot) -> str:
    """Return a JSON string snapshot of the bot's user-editable fields.

    The bot's ``id`` and relationship fields are deliberately omitted:
    snapshots are scoped to the bot, and versions travel with their
    ``bot_id`` via the column itself.
    """
    cats_raw = bot.categories or "[]"
    try:
        cats = json.loads(cats_raw) if isinstance(cats_raw, str) else cats_raw
    except (json.JSONDecodeError, TypeError):
        cats = []
    if not isinstance(cats, list):
        cats = []

    alt_raw = bot.alternate_greetings or "[]"
    try:
        alt = json.loads(alt_raw) if isinstance(alt_raw, str) else alt_raw
    except (json.JSONDecodeError, TypeError):
        alt = []
    if not isinstance(alt, list):
        alt = []

    payload = {
        "name": bot.name or "",
        "description": bot.description or "",
        "personality": bot.personality or "",
        "first_message": bot.first_message or "",
        "scenario": bot.scenario or "",
        "avatar_path": bot.avatar_path,
        "categories": cats,
        "bot_type": bot.bot_type or "rp",
        "alternate_greetings": alt,
        "mes_example": getattr(bot, "mes_example", "") or "",
        "dynamic_system_prompt": getattr(bot, "dynamic_system_prompt", "") or "",
        "world_state_prompt": getattr(bot, "world_state_prompt", "") or "",
    }
    return json.dumps(payload, ensure_ascii=False)


def deserialize_snapshot(snapshot_json: str) -> dict:
    """Parse a snapshot JSON string into the dict shape ``update`` expects."""
    try:
        data = json.loads(snapshot_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Corrupt snapshot JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Snapshot is not a JSON object")
    return data


class BotVersionService:
    def __init__(
        self,
        versions: BotVersionRepository,
        bots: BotRepository,
    ):
        self._versions = versions
        self._bots = bots

    # ── CRUD ────────────────────────────────────────────────────────

    async def create_version(
        self,
        bot_id: int,
        note: str = "",
        source: str = "manual",
    ) -> BotVersion:
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot {bot_id} was not found")

        max_v = await self._versions.get_max_version(bot_id)
        version = BotVersion(
            bot_id=bot_id,
            version_number=max_v + 1,
            snapshot_json=serialize_bot(bot),
            note=note or "",
            source=source,
        )
        version_id = await self._versions.add(version)
        version.id = version_id
        return version

    async def list_versions(self, bot_id: int) -> list[BotVersion]:
        # Validate bot exists so the UI gets a clean 404 instead of an
        # empty list when a stale bot id is in the URL.
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot {bot_id} was not found")
        return await self._versions.list_by_bot(bot_id)

    async def get_version(self, version_id: int) -> BotVersion:
        version = await self._versions.get(version_id)
        if version is None:
            raise NotFoundError(f"Version {version_id} not found")
        return version

    async def delete_version(self, version_id: int) -> None:
        version = await self._versions.get(version_id)
        if version is None:
            raise NotFoundError(f"Version {version_id} not found")
        await self._versions.delete(version_id)

    # ── Restore ─────────────────────────────────────────────────────

    async def restore_version(self, version_id: int) -> BotVersion:
        """Restore the bot to the state captured in ``version_id``.

        Steps:
            1. Auto-save the LIVE bot as a new version (source="auto",
               note pre-filled) so the user can always undo.
            2. Apply the snapshot fields back onto the bot via the
               BotRepository update path.
        """
        version = await self._versions.get(version_id)
        if version is None:
            raise NotFoundError(f"Version {version_id} not found")

        # 1. Auto-snapshot the live state BEFORE mutating it.
        await self.create_version(
            bot_id=version.bot_id,
            note=f"Auto-saved before restore to v{version.version_number}",
            source="auto",
        )

        # 2. Apply the snapshot.
        data = deserialize_snapshot(version.snapshot_json)
        # For fields added in 0.0.4 (floating system prompt + world
        # state prompt) we use ``None`` as the sentinel for "this
        # snapshot predates the field". The SQL repository treats
        # ``None`` as "don't touch the live value" (see
        # ``SqlAlchemyBotRepository.update``), so a pre-0.0.4 snapshot
        # round-trips without wiping the bot's live prompts. An
        # explicit ``""`` in the snapshot DOES clear the field — the
        # operator authored that snapshot knowing they wanted to
        # blank it. Caught by ``test_restore_old_snapshot_preserves_new_fields``.
        dynamic_prompt = data.get("dynamic_system_prompt")
        world_state_prompt = data.get("world_state_prompt")
        await self._bots.update(
            version.bot_id,
            name=data.get("name", ""),
            personality=data.get("personality", ""),
            first_message=data.get("first_message", ""),
            scenario=data.get("scenario", ""),
            description=data.get("description", ""),
            avatar_path=data.get("avatar_path"),
            categories=data.get("categories") or [],
            bot_type=data.get("bot_type", "rp"),
            alternate_greetings=data.get("alternate_greetings") or [],
            mes_example=data.get("mes_example", ""),
            dynamic_system_prompt=dynamic_prompt,
            world_state_prompt=world_state_prompt,
        )
        return version


def to_dto(version: BotVersion, *, include_snapshot: bool = False) -> BotVersionDTO:
    """Convert a ``BotVersion`` row to its API DTO.

    ``include_snapshot`` is False by default for list responses —
    snapshots can be tens of KB and the timeline only needs metadata.
    """
    snapshot = None
    if include_snapshot:
        try:
            snapshot = json.loads(version.snapshot_json)
        except (json.JSONDecodeError, TypeError):
            snapshot = None
    return BotVersionDTO(
        id=version.id,
        bot_id=version.bot_id,
        version_number=version.version_number,
        note=version.note or "",
        source=version.source or "manual",
        created_at=version.created_at,
        snapshot=snapshot,
    )
