"""Tests for Skills injection in the orchestrator's prompt assembly.

See spec §7. CRITICAL: covers BOTH prompt-assembly paths
(``_node_system_prompt`` graph path + ``_build_all_messages``
streaming path) because they must stay in sync — see AGENTS.md
§2 "parallel paths" rule.

The Skills block is appended to the system prompt right after
``<Persona>/<Scenario>`` so the LLM sees the behavioural rules in
a stable position regardless of any per-turn injections
(``[Reminder]``, ``[World state from previous turn]``).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.application.dto import (
    ConversationRequest,
    SkillDTO,
)
from app.infrastructure.orchestration.langgraph_orchestrator import (
    LangGraphConversationOrchestrator,
)

# ── Stubs ────────────────────────────────────────────────────────


class _StubLLM:
    """Returns a fixed chunk so we can assert on the final messages array."""

    async def generate_response(self, messages, **_kwargs):
        yield type(
            "Chunk",
            (),
            {
                "content": "ok",
                "reasoning": None,
                "usage": None,
                "debug_messages": messages,
            },
        )()


class _StubPreamble:
    def fallback(self) -> str:
        return ""

    def get(self, _bot_type):
        return ""


def _build_orchestrator() -> LangGraphConversationOrchestrator:
    from app.infrastructure.config import Settings

    settings = Settings(_env_file=None)
    return LangGraphConversationOrchestrator(
        llm=_StubLLM(),  # type: ignore[arg-type]
        settings=settings,
        preamble_provider=_StubPreamble(),  # type: ignore[arg-type]
    )


def _make_skill(id: int, name: str, description: str = "d", instruction: str = "i") -> SkillDTO:
    """Factory for SkillDTO instances used across the tests."""
    return SkillDTO(
        id=id,
        name=name,
        description=description,
        instruction=instruction,
        tags=[],
        created_at=datetime(2026, 7, 17, 0, 0, 0),
        updated_at=datetime(2026, 7, 17, 0, 0, 0),
    )


def _make_request(*, skills: list[SkillDTO] | None = None) -> ConversationRequest:
    return ConversationRequest(
        thread_id=1,
        bot_id=1,
        user_input="hi",
        bot_name="Lili",
        bot_personality="friendly",
        bot_scenario="",
        first_message="",
        bot_type="rp",
        history=[],
        untrusted_context=[],
        skills=skills or [],
    )


# ── Graph path: _node_system_prompt ─────────────────────────────


def test_skills_block_injected_in_node_system_prompt_when_skills_present():
    """When the request carries skills, the system prompt contains a
    ``<Skills>...</Skills>`` block with each skill listed."""
    orch = _build_orchestrator()
    request = _make_request(
        skills=[
            _make_skill(1, "Sarcastic", "dry wit", "apply when user uses sarcasm"),
            _make_skill(2, "Concise", "short replies", "apply when short input"),
        ]
    )
    state: dict[str, Any] = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    new_state = orch._node_system_prompt(state)
    messages = new_state["messages"]

    # Find the skills block.
    skills_msgs = [m for m in messages if m["role"] == "system" and "<Skills>" in m["content"]]
    assert len(skills_msgs) == 1, "expected exactly one <Skills> system message"
    content = skills_msgs[0]["content"]
    assert "</Skills>" in content
    assert "Sarcastic" in content
    assert "Concise" in content
    assert "dry wit" in content
    assert "short replies" in content


def test_skills_block_skipped_when_no_skills():
    """Empty skills list → no <Skills> block in the system prompt."""
    orch = _build_orchestrator()
    request = _make_request(skills=[])
    state = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    new_state = orch._node_system_prompt(state)
    messages = new_state["messages"]

    skills_msgs = [m for m in messages if "<Skills>" in m["content"]]
    assert skills_msgs == []


def test_skills_block_positioned_after_persona_block():
    """<Skills> block lands AFTER <Persona>...</Persona> in message order.

    See spec §7.2 — the LLM should see the rules in a stable
    position. Persona first, skills right after, before any
    per-turn injections.
    """
    orch = _build_orchestrator()
    request = _make_request(
        skills=[_make_skill(1, "Sarcastic")],
    )
    state = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    new_state = orch._node_system_prompt(state)
    messages = new_state["messages"]

    # Find indices of <Persona> and <Skills> system messages.
    persona_idx = next(
        i for i, m in enumerate(messages) if "<Persona>" in m["content"]
    )
    skills_idx = next(
        i for i, m in enumerate(messages) if "<Skills>" in m["content"]
    )
    assert skills_idx == persona_idx + 1, (
        f"<Skills> should immediately follow <Persona>; "
        f"got persona_idx={persona_idx}, skills_idx={skills_idx}"
    )


def test_skills_block_format_xml_paired():
    """The block uses XML-paired tags (parity with <Persona>/<Scenario>).

    Confirms the exact format the LLM will see — useful for the
    dev-mode debug modal that displays the assembled prompt.
    """
    orch = _build_orchestrator()
    request = _make_request(
        skills=[
            _make_skill(1, "Sarcastic", description="dry wit", instruction="i"),
        ]
    )
    state = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    new_state = orch._node_system_prompt(state)
    skills_msg = next(
        m for m in new_state["messages"] if "<Skills>" in m["content"]
    )
    content = skills_msg["content"]
    # Must start with <Skills> and end with </Skills>.
    assert content.startswith("<Skills>")
    assert content.rstrip().endswith("</Skills>")
    # And use bullet list inside (parity with format-standart-rp output).
    assert "- **Sarcastic**" in content


def test_skills_block_falls_back_to_truncated_instruction_when_description_empty():
    """If description is empty, fall back to the first 200 chars of
    instruction (with ellipsis). Matches spec §7.1 — keeps catalog
    concise even when authors leave the short description blank.
    """
    orch = _build_orchestrator()
    long_instruction = "A" * 500  # longer than 200 chars
    request = _make_request(
        skills=[_make_skill(1, "EmptyDesc", description="", instruction=long_instruction)],
    )
    state = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    new_state = orch._node_system_prompt(state)
    skills_msg = next(
        m for m in new_state["messages"] if "<Skills>" in m["content"]
    )
    content = skills_msg["content"]
    # First 200 chars of the instruction appear, with "…" suffix.
    assert "A" * 200 in content
    assert "…" in content
    # The full 500-A instruction is NOT in the catalog block.
    assert "A" * 201 not in content


# ── Streaming path: _build_all_messages ─────────────────────────


def test_skills_block_injected_in_build_all_messages_when_skills_present():
    """Streaming path mirrors graph path. CRITICAL for AGENTS.md §2. """
    orch = _build_orchestrator()
    request = _make_request(
        skills=[_make_skill(1, "Sarcastic", description="dry wit")],
    )
    messages = orch._build_all_messages(request)

    skills_msgs = [m for m in messages if m["role"] == "system" and "<Skills>" in m["content"]]
    assert len(skills_msgs) == 1
    assert "Sarcastic" in skills_msgs[0]["content"]


def test_skills_block_skipped_in_build_all_messages_when_no_skills():
    """Streaming path also skips the block on empty list."""
    orch = _build_orchestrator()
    request = _make_request(skills=[])
    messages = orch._build_all_messages(request)

    skills_msgs = [m for m in messages if "<Skills>" in m["content"]]
    assert skills_msgs == []


# ── Cross-path consistency ────────────────────────────────────────


def test_graph_and_streaming_paths_produce_identical_skill_blocks():
    """The two prompt-assembly paths must produce the same <Skills> block
    (modulo order around per-turn injections which differ — see
    _build_all_messages which has a slightly different structure for
    streaming).

    This is the most important regression guard for the Skills
    feature: a divergent <Skills> between paths means the LLM
    sees different behaviour rules depending on the path taken.
    """
    orch = _build_orchestrator()
    skills = [
        _make_skill(1, "Sarcastic", description="dry wit", instruction="apply when"),
        _make_skill(2, "Concise", description="short", instruction="keep brief"),
    ]
    request = _make_request(skills=skills)

    # Graph path: _node_system_prompt produces initial messages,
    # then the rest of the graph runs. We only need the system_prompt
    # node's output for the skills block check.
    graph_state: dict[str, Any] = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    graph_skills = next(
        m["content"] for m in orch._node_system_prompt(graph_state)["messages"]
        if "<Skills>" in m["content"]
    )

    # Streaming path: _build_all_messages produces the full list.
    stream_skills = next(
        m["content"] for m in orch._build_all_messages(request)
        if "<Skills>" in m["content"]
    )

    # The block content must match exactly (same XML format,
    # same order of skills, same framing).
    assert graph_skills == stream_skills


# ── Cross-feature: skills + dynamic prompt coexist ───────────────


def test_skills_coexists_with_dynamic_system_prompt_via_user_input():
    """Skills block lives in system_prompt node (early in the graph).
    Dynamic prompt lives in user_input node (late in the graph).
    They must NOT collide — both end up in the final messages list.
    """
    orch = _build_orchestrator()
    request = _make_request(
        skills=[_make_skill(1, "Sarcastic")],
    )
    request_with_reminder = ConversationRequest(
        thread_id=1,
        bot_id=1,
        user_input="hi",
        bot_name="Lili",
        bot_personality="friendly",
        bot_scenario="",
        first_message="",
        bot_type="rp",
        history=[],
        untrusted_context=[],
        skills=request.skills,
        dynamic_system_prompt="Stay in character",
    )

    # Run the system_prompt node to get skills + persona.
    state: dict[str, Any] = {
        "request": request_with_reminder,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    state = orch._node_system_prompt(state)
    # Then the user_input node to add the reminder.
    state = orch._node_user_input(state)

    messages = state["messages"]
    # Skills block present.
    assert any("<Skills>" in m["content"] for m in messages)
    # Reminder block present.
    assert any("[Reminder] Stay in character" in m["content"] for m in messages)
    # Both system messages, in the right relative order:
    # <Persona> (idx 0) → <Skills> (idx 1) → ... → [Reminder] (near end)
    skills_idx = next(
        i for i, m in enumerate(messages) if "<Skills>" in m["content"]
    )
    reminder_idx = next(
        i for i, m in enumerate(messages) if "[Reminder]" in m["content"]
    )
    assert skills_idx < reminder_idx, (
        "Skills should be in the early system-prompt block; "
        "reminder is per-turn and comes later"
    )
