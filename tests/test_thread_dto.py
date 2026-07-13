"""Tests for ThreadDTO — the new parent_thread_id field is critical
for the thread-tree UI. The DTO construction sites in
SqlAlchemyThreadRepository (get, list_for_bot, find_by_bot_and_persona)
all populate this field from the SQLAlchemy row attribute. If the
field is dropped from the DTO, the tree UI silently renders as
a flat list — a regression the unit test guards against.
"""

from app.application.dto import ThreadDTO


def test_thread_dto_accepts_parent_thread_id() -> None:
    """ThreadDTO carries the new field for fork-lineage UI."""
    t = ThreadDTO(
        id=1,
        bot_id=2,
        name="Fork of original",
        parent_thread_id=42,
    )
    assert t.parent_thread_id == 42


def test_thread_dto_parent_thread_id_defaults_to_none() -> None:
    """Root threads have parent_thread_id = None (the default)."""
    t = ThreadDTO(id=1, bot_id=2, name="Original")
    assert t.parent_thread_id is None


def test_thread_dto_parent_thread_id_serializes_in_dump() -> None:
    """``model_dump`` includes the field (the API contract)."""
    t = ThreadDTO(id=1, bot_id=2, name="Fork", parent_thread_id=99)
    dumped = t.model_dump()
    assert "parent_thread_id" in dumped
    assert dumped["parent_thread_id"] == 99
