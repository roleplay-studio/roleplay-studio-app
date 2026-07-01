import logging

from app.application.dto import CreateBotCommand, UpdateBotCommand
from app.application.exceptions import NotFoundError
from app.application.ports import BotRepository, BotVersionRepository
from app.application.services.bot_version import serialize_bot

logger = logging.getLogger(__name__)


class BotService:
    def __init__(
        self,
        bots: BotRepository,
        bot_versions: BotVersionRepository | None = None,
    ):
        self._bots = bots
        self._bot_versions = bot_versions

    async def create_bot(self, command: CreateBotCommand) -> int:
        return await self._bots.create(
            command.name.strip(),
            command.personality.strip(),
            command.first_message.strip(),
            scenario=command.scenario,
            description=command.description,
            avatar_path=command.avatar_path,
            categories=command.categories,
            bot_type=command.bot_type,
            alternate_greetings=command.alternate_greetings,
            mes_example=command.mes_example,
        )

    async def update_bot(self, command: UpdateBotCommand) -> None:
        # 1. Snapshot the bot BEFORE mutation so we can compare.
        #    We capture the JSON snapshot string up front (not a
        #    reference to the ORM row) because ``bot.update`` mutates
        #    the row in place — holding a reference would compare the
        #    new state against itself.
        pre = await self._bots.get(command.bot_id)
        if pre is None:
            raise NotFoundError(f"Bot {command.bot_id} was not found")
        pre_snapshot = serialize_bot(pre)

        await self._bots.update(
            command.bot_id,
            command.name.strip(),
            command.personality.strip(),
            command.first_message.strip(),
            scenario=command.scenario,
            description=command.description,
            avatar_path=command.avatar_path,
            categories=command.categories,
            bot_type=command.bot_type,
            alternate_greetings=command.alternate_greetings,
            mes_example=command.mes_example,
        )

        # 2. Auto-version: only if a version repo is wired AND the
        #    bot actually changed (skip no-op saves).
        if self._bot_versions is None:
            return

        post = await self._bots.get(command.bot_id)
        if post is None:
            return
        post_snapshot = serialize_bot(post)
        if pre_snapshot == post_snapshot:
            return

        max_v = await self._bot_versions.get_max_version(command.bot_id)
        from app.infrastructure.db.models import BotVersion

        # Auto-snapshot stores the PRE-change state — that's the state
        # a user would want to roll back to. Storing POST would just
        # be the same as the current bot, which makes restore useless.
        version = BotVersion(
            bot_id=command.bot_id,
            version_number=max_v + 1,
            snapshot_json=pre_snapshot,
            note="",
            source="auto",
        )
        await self._bot_versions.add(version)

    async def get_bot(self, bot_id: int):
        """Return raw SQLModel Bot (or None if not found)."""
        return await self._bots.get(bot_id)

    async def get_bot_with_count(self, bot_id: int):
        """Return (Bot, thread_count) or raise NotFoundError."""

        bot = await self._bots.get(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot {bot_id} was not found")
        if hasattr(self._bots, "get_with_thread_counts"):
            bots_with = await self._bots.get_with_thread_counts()
            for b, c in bots_with:
                if b.id == bot_id:
                    return b, c
        return bot, 0

    async def list_bots_with_counts(self):
        """Return list of (Bot, thread_count) tuples."""
        if hasattr(self._bots, "get_with_thread_counts"):
            return await self._bots.get_with_thread_counts()
        return [(bot, 0) for bot in await self._bots.list()]

    async def list_bots(self):
        """Return raw list of SQLModel Bot (backward compat)."""
        return await self._bots.list()

    async def delete_bot(self, bot_id: int) -> None:
        await self._bots.delete(bot_id)
