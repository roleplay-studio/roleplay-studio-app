"""Regression: ``regenerate_message`` must stamp the floating-prompt
snapshot the LLM received onto the persisted branch row.

Before the fix, ``ChatService.regenerate_message`` called
``MessageRepository.save_branch`` without forwarding
``request.dynamic_system_prompt``. As a result the LLM did receive
the [Reminder] block (orchestrator path), but the chat UI panel
"Dynamic system prompt" was empty because the persisted row had no
``dynamic_system_prompt`` field. This locks the contract so any
future drift is caught in CI.

Mirrors the ``tests/test_state_regenerate_route.py`` boot path:
``Settings.from_env`` is monkeypatched so the Alembic bootstrap
doesn't read the developer's real ``.env`` file.
"""

from __future__ import annotations

import os

import pytest

from app.application.dto import CreateBotCommand
from app.bootstrap import init_container
from app.infrastructure.config import Settings
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyMessageRepository,
)


@pytest.fixture
async def boot(tmp_path, monkeypatch):
    db_path = str(tmp_path / "v.db")
    settings = Settings(_env_file=None, db_path=db_path)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    # ``init_container`` runs the alembic migrations as part of
    # constructing the container — exactly the path FastAPI takes
    # through ``init_container()`` in the lifespan handler.
    container = await init_container(settings=settings)

    yield {
        "settings": settings,
        "container": container,
        "bots": container.bots,
        "threads": container.threads,
    }
    if os.path.exists(settings.db_path):
        try:
            os.remove(settings.db_path)
        except OSError:
            pass


async def test_save_branch_persists_dynamic_system_prompt(boot) -> None:
    """The whole point of the fix: ``dynamic_system_prompt`` reaches
    the persisted branch so the chat UI panel can render it.
    """

    bot_id = await boot["bots"].create_bot(
        CreateBotCommand(name="dynamic-prompt-bot", personality="x")
    )

    msgs_repo = SqlAlchemyMessageRepository(boot["container"].store)
    thread_id = await boot["threads"].create_thread(bot_id=bot_id, persona_id=None)

    new_id = await msgs_repo.save_branch(
        thread_id=thread_id,
        role="assistant",
        content="regenerated answer",
        branch_group="bg-dyn-prompt",
        branch_index=1,
        generation_status="complete",
        dynamic_system_prompt="[Reminder] Stay in character, respond in Russian.",
    )
    assert new_id is not None
    versions = await msgs_repo.get_versions(new_id)
    assert versions, "save_branch must return row that get_versions can find"
    row = versions[-1]
    assert row.id == new_id
    assert row.dynamic_system_prompt == "[Reminder] Stay in character, respond in Russian.", (
        f"regenerated branch must carry the floating-prompt snapshot; "
        f"got {row.dynamic_system_prompt!r}"
    )


async def test_save_branch_without_dynamic_prompt_is_none(boot) -> None:
    """Not every regenerate is from a bot with a floating prompt;
    ``dynamic_system_prompt=None`` should stay ``None``, not become ``''``.
    """

    bot_id = await boot["bots"].create_bot(CreateBotCommand(name="plain-bot", personality="x"))
    msgs_repo = SqlAlchemyMessageRepository(boot["container"].store)
    thread_id = await boot["threads"].create_thread(bot_id=bot_id, persona_id=None)

    new_id = await msgs_repo.save_branch(
        thread_id=thread_id,
        role="assistant",
        content="regenerated answer",
        branch_group="bg-plain",
        branch_index=1,
        generation_status="complete",
    )
    versions = await msgs_repo.get_versions(new_id)
    row = versions[-1]
    assert row.dynamic_system_prompt is None
