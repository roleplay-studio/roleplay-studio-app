"""SkillService — business logic for skill CRUD and bot attachment. See spec §6.2.

Layered between the API/route layer and the persistence layer:
- Routes call ``SkillService`` methods.
- ``SkillService`` validates (length, uniqueness, limit) and translates
  ``SkillRepository`` errors (``ValueError`` on duplicate, ``DeleteSkillResult``
  on delete-in-use) into the application-layer exception hierarchy
  (``ValidationError``, ``ConflictError``).
- Persistence stays behind ``SkillRepository`` Protocol — services never
  import infrastructure directly (clean architecture per AGENTS.md §1).
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.application.dto import (
    BotSkillDTO,
    CreateSkillCommand,
    SkillDTO,
    UpdateSkillCommand,
)
from app.application.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.application.ports import SkillRepository
from app.infrastructure.config import Settings
from app.infrastructure.db.models import Bot, GlobalSkill

logger = logging.getLogger(__name__)


class SkillService:
    """Application-layer service for the Skills feature.

    Holds no state of its own beyond the injected repository + settings.
    See spec §6.2 for the method-by-method contract.
    """

    def __init__(self, store, settings: Settings) -> None:
        # The repository wraps the same store; constructed internally
        # rather than injected so the route layer only needs to wire
        # one object (the store) into the container.
        self._store = store
        self._repo: SkillRepository = self._make_repo(store)
        self._settings = settings

    @staticmethod
    def _make_repo(store) -> SkillRepository:
        # Local import avoids the application → infrastructure cycle at
        # module load time (mirrors the pattern in
        # ``app.application.services.settings.SettingsService``).
        from app.infrastructure.repositories.sqlalchemy import (
            SqlAlchemySkillRepository,
        )

        return SqlAlchemySkillRepository(store)

    # ── Read paths ──────────────────────────────────────────────

    async def list_skills(
        self,
        q: str | None = None,
        tag: str | None = None,
    ) -> list[SkillDTO]:
        """List all skills, optionally filtered by ``q`` / ``tag``."""
        skills = await self._repo.list_all(q=q, tag=tag)
        return [self._to_dto(s) for s in skills]

    async def get_skill(self, skill_id: int) -> SkillDTO:
        """Fetch a single skill. Raises ``NotFoundError`` if missing."""
        skill = await self._repo.get(skill_id)
        if skill is None:
            raise NotFoundError(f"Skill {skill_id} not found")
        return self._to_dto(skill)

    async def list_for_bot_with_ids(self, skill_ids: list[int]) -> list[SkillDTO]:
        """Resolve a list of skill IDs → ``SkillDTO`` list.

        Used by ``ChatService._build_request`` after reading
        ``Bot.skill_ids`` — the hot path for every chat turn. Order
        preserved by id ASC (per spec §6.1); orphan ids silently
        omitted.
        """
        if not skill_ids:
            return []
        skills = await self._repo.list_by_ids(skill_ids)
        return [self._to_dto(s) for s in skills]

    # ── Write paths ─────────────────────────────────────────────

    async def create_skill(self, command: CreateSkillCommand) -> int:
        """Create a new skill. Raises ``ValidationError`` on duplicate name.

        The repository raises ``ValueError`` on duplicate name (parity
        with other repos in this codebase — see e.g. how
        ``app.application.services.bot.BotService`` maps IntegrityError
        to ValidationError). We map to ``ValidationError`` with
        ``http_status=409`` here so the existing exception handler in
        ``api/main.py`` returns a 409 Conflict, which is the correct
        semantic for "this resource already exists".
        """
        try:
            return await self._repo.create(
                name=command.name,
                description=command.description,
                instruction=command.instruction,
                tags=command.tags,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), http_status=409) from exc

    async def update_skill(
        self,
        skill_id: int,
        command: UpdateSkillCommand,
    ) -> None:
        """Partial update. Raises ``NotFoundError`` / ``ValidationError``.

        Special case: if the update changes ``name``, we pre-check
        uniqueness against the catalog. The repo's own uniqueness
        check only fires on insert, so we have to do this in the
        service layer. We skip the check when the new name matches
        the existing one (no-op rename).
        """
        if command.name is not None:
            existing = await self._repo.get(skill_id)
            if existing is None:
                raise NotFoundError(f"Skill {skill_id} not found")
            # No-op rename: the same name shouldn't trigger duplicate.
            if existing.name != command.name:
                # Look for any other skill with the requested name.
                # Repo.list_all(q=...) is case-insensitive substring, so
                # we still need to filter to exact match.
                candidates = await self._repo.list_all(q=command.name)
                for s in candidates:
                    if s.id != skill_id and s.name == command.name:
                        raise ValidationError(
                            f"Skill with name {command.name!r} already exists",
                            http_status=409,
                        )

        await self._repo.update(
            skill_id,
            name=command.name,
            description=command.description,
            instruction=command.instruction,
            tags=command.tags,
        )

    async def delete_skill(self, skill_id: int) -> None:
        """Delete a skill. Raises ``ConflictError`` / ``NotFoundError``.

        The repository's ``delete`` returns a ``DeleteSkillResult``:
        - ``deleted=True`` → success
        - ``deleted=False`` + ``attached_to=[ids]`` → in use, raise Conflict
        - ``deleted=False`` + empty attached_to → row didn't exist

        The third case is ambiguous at the repo level (could be "no row"
        OR "row with empty skill_ids refs which can't happen"), so we
        probe via ``repo.get`` to disambiguate.
        """
        result = await self._repo.delete(skill_id)
        if result.deleted:
            return
        if result.attached_to:
            raise ConflictError(
                f"Skill {skill_id} is attached to {len(result.attached_to)} bot(s)",
                attached_to=result.attached_to,
            )
        # Repo said not-deleted with no attachments — must be missing.
        raise NotFoundError(f"Skill {skill_id} not found")

    async def update_bot_skills(
        self,
        bot_id: int,
        skill_ids: list[int],
    ) -> list[SkillDTO]:
        """Replace ``Bot.skill_ids`` with the new list.

        Validates:
        - length ≤ ``Settings.skills_max_per_bot``
        - all ids exist in the global catalog

        Returns the resolved ``SkillDTO`` list (post-dedup, in id-ASC
        order) so the route can serialise directly into the response.
        """
        # 1. Dedup (preserve insertion order)
        seen: set[int] = set()
        deduped: list[int] = []
        for sid in skill_ids:
            if sid not in seen:
                seen.add(sid)
                deduped.append(sid)

        # 2. Enforce max-per-bot limit
        max_allowed = self._settings.skills_max_per_bot
        if len(deduped) > max_allowed:
            raise ValidationError(
                f"Bot has {len(deduped)} skills, exceeds skills_max_per_bot={max_allowed}",
                http_status=400,
            )

        # 3. Validate all ids exist (bulk fetch; unknown ids surface as
        #    the diff between requested and returned id sets).
        if deduped:
            found = await self._repo.list_by_ids(deduped)
            found_ids = {s.id for s in found}
            missing = [sid for sid in deduped if sid not in found_ids]
            if missing:
                raise NotFoundError(f"Skill(s) not found: {missing}")

        # 4. Verify the bot exists before persisting — otherwise
        #    UPDATE matches 0 rows silently and the caller can't tell.
        async with self._store._async_session_factory() as session:
            existing = (
                await session.execute(select(Bot.id).where(Bot.id == bot_id))
            ).first()
            if existing is None:
                raise NotFoundError(f"Bot {bot_id} not found")

        # 5. Persist the new skill_ids list (sorted for stable on-disk
        #    representation; makes diff inspection easier).
        sorted_ids = sorted(deduped)
        async with self._store._async_session_factory() as session:
            stmt = (
                sa_update(Bot)
                .where(Bot.id == bot_id)
                .values(skill_ids=json.dumps(sorted_ids))
            )
            await session.execute(stmt)
            await session.commit()

        # 6. Return resolved DTOs (in id-ASC order, per spec §6.1).
        return await self.list_for_bot_with_ids(sorted_ids)

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _to_dto(skill: GlobalSkill) -> SkillDTO:
        """Project a SQLAlchemy row into the wire shape.

        Single source of truth for the GlobalSkill → SkillDTO mapping.
        Used by every read path in this class.
        """
        return SkillDTO(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            instruction=skill.instruction,
            tags=json.loads(skill.tags or "[]"),
            created_at=skill.created_at,
            updated_at=skill.updated_at,
        )

    @staticmethod
    def to_bot_dto(skill: GlobalSkill) -> BotSkillDTO:
        """Lightweight projection for ``BotResponse.skills``.

        Excludes ``instruction`` to keep the bot-list endpoint payload
        small. Use :meth:`SkillService.get_skill` for the full version.
        """
        return BotSkillDTO(
            id=skill.id,
            name=skill.name,
            description=skill.description,
        )
