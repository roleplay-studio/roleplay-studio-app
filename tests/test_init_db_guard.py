"""m11 regression test — ``SqlAlchemyStore.init_db`` is idempotent.

Covers the fix for m11 (docs/review.md): the previous implementation
re-ran ``alembic upgrade head`` every time init_db was called.
That's safe in theory (Alembic is idempotent) but costs:

* ``asyncio.to_thread`` spin-up
* ``alembic.config.Config`` parsing
* ``Path`` resolution
* ``os.chdir`` dance

on the hot path of every application startup. The fix: a
``_db_initialized`` flag flipped on first success — subsequent calls
short-circuit with a debug log.

The full fix (move init_db into a k8s init-container / Job) is
tracked separately; for the single-binary deployment a per-process
guard is sufficient.
"""

from __future__ import annotations

import pytest

from app.infrastructure.config import Settings
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyStore


@pytest.mark.asyncio
async def test_init_db_second_call_is_noop(tmp_path, monkeypatch):
    """After init_db succeeds once, a second call must skip the heavy
    upgrade path. We assert that by counting how many times the
    internal ``_run`` is invoked — the test patches the global
    ``alembic.command`` symbol that init_db reaches into."""
    settings = Settings(_env_file=None, db_path=str(tmp_path / "test.db"))
    store = SqlAlchemyStore(settings=settings)

    # Patch the alembic command symbol so we can count invocations
    # without actually running a migration. The point of the test
    # is the re-entrancy guard, not the migration outcome. Note:
    # init_db does ``from alembic import command`` *inside* the
    # function, so we monkey-patch ``alembic.command.upgrade`` —
    # init_db's local ``command`` resolves to the patched function.
    import alembic.command

    call_count = 0

    def _fake_run(_alembic_cfg, _target="head"):
        nonlocal call_count
        call_count += 1

    monkeypatch.setattr(alembic.command, "upgrade", _fake_run)

    # First call → must reach upgrade (counter == 1).
    await store.init_db()
    assert call_count == 1, "first init_db should run alembic upgrade"
    assert getattr(store, "_db_initialized", False) is True

    # Second call → must short-circuit (counter still 1).
    await store.init_db()
    assert call_count == 1, "second init_db must be a no-op (m11 guard)"


@pytest.mark.asyncio
async def test_init_db_guard_does_not_block_retry_on_failure(tmp_path, monkeypatch):
    """If init_db *fails* (upgrade raises), the guard must NOT flip
    to True — callers should be able to retry."""
    settings = Settings(_env_file=None, db_path=str(tmp_path / "test.db"))
    store = SqlAlchemyStore(settings=settings)

    call_count = 0

    def _flaky_run(_alembic_cfg, _target="head"):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated migration failure")

    import alembic.command

    monkeypatch.setattr(alembic.command, "upgrade", _flaky_run)

    with pytest.raises(RuntimeError, match="simulated migration failure"):
        await store.init_db()
    assert getattr(store, "_db_initialized", False) is False

    # Second call should attempt the upgrade again (no guard).
    await store.init_db()
    assert call_count == 2, "failed init_db must not flip the guard (retry path)"


@pytest.mark.asyncio
async def test_init_db_guard_initialized_attribute_default_false(tmp_path):
    """``_db_initialized`` defaults to False so a fresh store can
    call init_db. This is a baseline check to catch accidental
    constructor-side initialization that would mask the guard."""
    settings = Settings(_env_file=None, db_path=str(tmp_path / "test.db"))
    store = SqlAlchemyStore(settings=settings)
    # Note: not using ``getattr(..., False)`` default — we want to
    # assert the attribute's *current* state, not the fallback.
    assert not hasattr(store, "_db_initialized") or store._db_initialized is False
