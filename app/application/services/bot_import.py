"""Import a bot from a V1/V2/V3 character card (PNG/WebP/JPG) or a starter card.

Orchestrates the full pipeline:

1. For character cards: parse the image bytes via :func:`parse_character_card`.
   For starter cards: caller has already parsed the dict via :mod:`api.bot_loader`.
2. Save the original image as the bot's avatar (with constrain + resize).
3. Create the bot via :class:`BotRepository` using a :class:`CreateBotCommand`.
4. Import the character book's entries as knowledge entries (character cards only).

The service depends on duck-typed ports (``BotRepository``,
``KnowledgeService``) so the application layer never imports from
``infrastructure/`` — a stub :class:`KnowledgeService` is sufficient.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from character_card import (
    CharacterCardData,
    parse_character_card,
)

from app.application.dto import AddKnowledgeEntryCommand
from app.application.ports import BotRepository
from app.infrastructure.image_utils import constrain_image, resize_avatar

logger = logging.getLogger(__name__)

# Image extensions we accept for character cards. Mirrors SillyTavern's
# accepted set.
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class BotImportService:
    """Create a Bot + its knowledge entries from a character card image."""

    def __init__(
        self,
        bot_repo: BotRepository,
        knowledge_service,  # KnowledgeService — duck-typed to avoid import cycle
        avatar_dir: str | Path,
    ):
        self._bots = bot_repo
        self._knowledge = knowledge_service
        self._avatar_dir = Path(avatar_dir)

    async def import_from_card(
        self,
        file_bytes: bytes,
        file_ext: str,
    ) -> int:
        """Parse a character card image, save avatar, create bot, import lore.

        Raises:
            CharacterCardParseError: bytes can't be parsed as a V1/V2/V3 card.
        """
        card = parse_character_card(file_bytes, file_ext)

        avatar_path = self.save_avatar_bytes(file_bytes, file_ext)

        composed_personality, used_description = self._compose_personality(card)
        # If the fallback chain pulled the V2 description into
        # ``Bot.personality`` (i.e. the author left the dedicated
        # ``personality`` field empty), the same long sheet must not
        # also be dumped into ``Bot.description`` — the BotEditPage
        # textarea would be 12k chars of character sheet that the
        # user has no way to distinguish from the actual field
        # purpose. Show only the creator notes instead.
        if used_description:
            description = card.creator_notes or ""
        else:
            description = card.description

        bot_id = await self._bots.create(
            card.name.strip(),
            composed_personality.strip(),
            card.first_message.strip(),
            scenario=self._compose_scenario(card).strip(),
            description=description,
            avatar_path=avatar_path,
            categories=card.tags,
            alternate_greetings=card.alternate_greetings,
            mes_example=card.mes_example,
        )

        for content in card.character_book_entries:
            if content and content.strip():
                await self._knowledge.add_entry(
                    AddKnowledgeEntryCommand(bot_id=bot_id, content=content.strip())
                )

        return bot_id

    async def import_from_starter(
        self,
        card: dict,
        avatar_bytes: bytes | None = None,
    ) -> int:
        """Create a Bot from an already-parsed starter card.

        ``card`` must contain at minimum: name, personality, first_message, scenario,
        categories (the same shape produced by :mod:`api.bot_loader`). When
        ``avatar_bytes`` is provided it's persisted as the bot's avatar (PNG path
        goes through the same constrain/resize pipeline as character cards);
        otherwise the bot is created with no avatar.
        """
        ext = ".png" if avatar_bytes else ""
        avatar_path = self.save_avatar_bytes(avatar_bytes, ext) if avatar_bytes else None

        return await self._bots.create(
            card["name"].strip(),
            card.get("personality", "").strip(),
            card.get("first_message", "").strip(),
            scenario=card.get("scenario", "").strip(),
            description="",
            avatar_path=avatar_path,
            categories=list(card.get("categories", []) or []),
            mes_example=card.get("mes_example", ""),
        )

    def save_avatar_bytes(self, file_bytes: bytes, file_ext: str) -> str:
        """Persist avatar bytes to the avatars dir, returning the public path.

        Public so the setup wizard can hand off PNG-карточка bytes without
        re-parsing them as a character card. The bytes go through the same
        constrain + resize pipeline as :meth:`import_from_card`.
        """
        os.makedirs(self._avatar_dir, exist_ok=True)
        ext = file_ext if file_ext in _IMAGE_EXTS else ".png"
        stem = uuid.uuid4().hex
        dest = self._avatar_dir / f"{stem}{ext}"
        dest.write_bytes(file_bytes)
        # Re-encode / constrain like the avatar-upload path does.
        try:
            constrain_image(str(dest), str(dest), max_dim=1024)
        except Exception:
            logger.warning("constrain_image failed for %s; keeping original", dest)
        try:
            resize_avatar(str(dest), self._avatar_dir, stem, ext)
        except Exception:
            logger.warning("resize_avatar failed for %s; keeping original", dest)
        return f"/uploads/avatars/{stem}{ext}"

    @staticmethod
    def _compose_personality(card: CharacterCardData) -> tuple[str, bool]:
        """Compose the Bot.personality from V2 fields.

        V2 splits the system-level guidance into several places:
        - ``personality`` — who the character is.
        - ``system_prompt`` — scenario/world-level LLM instructions
          (folded into ``Bot.scenario`` by :meth:`_compose_scenario`).
        - ``post_history_instructions`` — per-turn output formatting
          rules. Stays attached to the character description.
        - ``description`` — the long character bio. **Some V2
          authors (e.g. character_card_creator, luna_the_dream_weaver)
          leave ``personality`` empty and put the whole sheet under
          ``description``.** Without a fallback the LLM would see
          an empty personality and the bot would have no character at
          runtime.

        We chain ``personality → system_prompt → description`` so the
        bot always has a non-empty personality signal. The second
        tuple element tells :meth:`import_from_card` whether the
        description was consumed for the fallback — when it was,
        ``Bot.description`` should hold only ``creator_notes`` (or
        be empty) so the long character sheet doesn't end up
        duplicated in two UI fields.
        """
        primary = (card.personality or "").strip()
        if primary:
            joined: list[str] = [primary]
            used_description = False
        else:
            sys_p = (card.system_prompt or "").strip()
            desc = (card.description or "").strip()
            if sys_p and desc:
                # Both blocks present and personality is empty — keep
                # both in personality (system_prompt is instructions,
                # description is the character sheet). The model gets
                # a richer block; the caller should not mark the
                # description as "used" because both fields are still
                # semantically distinct.
                joined = [sys_p, desc]
                used_description = False
            elif sys_p:
                joined = [sys_p]
                used_description = False
            elif desc:
                joined = [desc]
                used_description = True
            else:
                joined = []
                used_description = False

        # post_history_instructions is the "always appended" tail —
        # applies whether the personality came from V2 or a fallback.
        post = (card.post_history_instructions or "").strip()
        if post:
            joined.append(post)

        return "\n\n---\n\n".join(p for p in joined if p), used_description

    @staticmethod
    def _compose_scenario(card: CharacterCardData) -> str:
        """Compose the Bot.scenario from V2 scenario + V2 system_prompt.

        Both fields describe the world / framing the bot operates in
        rather than the character itself, so they belong in
        ``Bot.scenario`` — which the orchestrator renders as the
        ``<Scenario>...</Scenario>`` block of the LLM system message.
        Empty fields are dropped; otherwise we join with the same
        ``---`` separator as the personality composer.
        """
        parts: list[str] = []
        for section in (card.scenario, card.system_prompt):
            if section and section.strip():
                parts.append(section.strip())
        return "\n\n---\n\n".join(parts)
