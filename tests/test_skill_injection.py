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
    """Streaming path mirrors graph path. CRITICAL for AGENTS.md §2.

    With the per-turn [Skills] safety net, the streaming path now
    produces TWO <Skills> blocks: the initial system-prompt block
    AND the per-turn re-injection. Both must be present.
    """
    orch = _build_orchestrator()
    request = _make_request(
        skills=[_make_skill(1, "Sarcastic", description="dry wit")],
    )
    messages = orch._build_all_messages(request)

    skills_msgs = [m for m in messages if m["role"] == "system" and "<Skills>" in m["content"]]
    assert len(skills_msgs) == 2, (
        f"expected 2 <Skills> blocks (initial + per-turn), got {len(skills_msgs)}"
    )
    assert "Sarcastic" in skills_msgs[0]["content"]
    assert "Sarcastic" in skills_msgs[1]["content"]


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


# ── Per-turn [Skills] re-injection (Skills safety net) ───────────
#
# Skills get injected twice per turn:
#   1. Initial system-prompt block (via _node_system_prompt /
#      _build_all_messages early branch) — survives when the
#      provider keeps the first system message under middle-out
#      truncation.
#   2. Per-turn block at the END of the prompt, right after
#      [Reminder] (and before [World state from previous turn]).
#      This is the **safety net**: providers that cut from the
#      middle of long conversations will still surface the skills
#      catalog because it's adjacent to the user turn.
#
# The two blocks must produce **identical content** (same XML
# format, same order, same skills) so the LLM sees the same rules
# regardless of which end of the prompt the model attends to.
# A divergent per-turn block is a silent regression.


def test_per_turn_skills_block_injected_in_node_user_input():
    """Graph path: _node_user_input appends a per-turn <Skills>...</Skills>
    block AFTER the [Reminder] block (or as the first per-turn injection
    when no reminder is set), and BEFORE [World state from previous turn].
    """
    orch = _build_orchestrator()
    request = ConversationRequest(
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
        skills=[
            _make_skill(1, "Sarcastic", description="dry wit"),
            _make_skill(2, "Concise", description="short replies"),
        ],
        dynamic_system_prompt="Stay in character",
        prev_world_state="loc: tavern",
    )
    # Prime state with the early system_prompt node so messages already
    # have the initial <Persona>/<Skills> in place.
    state: dict[str, Any] = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    state = orch._node_system_prompt(state)
    state = orch._node_user_input(state)
    messages = state["messages"]

    # Count <Skills> blocks. We expect TWO: initial (from _node_system_prompt)
    # + per-turn (from _node_user_input). Both must be system messages.
    skills_msgs = [
        m for m in messages
        if m["role"] == "system" and "<Skills>" in m["content"]
    ]
    assert len(skills_msgs) == 2, (
        f"expected 2 <Skills> blocks (initial + per-turn), got {len(skills_msgs)}"
    )
    # Per-turn block content matches the catalog format.
    per_turn = skills_msgs[1]["content"]
    assert "Sarcastic" in per_turn and "Concise" in per_turn
    assert per_turn.startswith("<Skills>")
    assert per_turn.rstrip().endswith("</Skills>")


def test_per_turn_skills_block_in_build_all_messages():
    """Streaming path: _build_all_messages appends a per-turn <Skills>
    block AFTER [Reminder] (or as the first per-turn injection when no
    reminder is set) and BEFORE [World state from previous turn].
    Mirrors the graph path's _node_user_input — see AGENTS.md §2.
    """
    orch = _build_orchestrator()
    request = ConversationRequest(
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
        skills=[_make_skill(1, "Sarcastic", description="dry wit")],
        dynamic_system_prompt="Stay in character",
        prev_world_state="loc: tavern",
    )
    messages = orch._build_all_messages(request)

    skills_msgs = [
        m for m in messages
        if m["role"] == "system" and "<Skills>" in m["content"]
    ]
    assert len(skills_msgs) == 2, (
        f"expected 2 <Skills> blocks (initial + per-turn), got {len(skills_msgs)}"
    )


def test_per_turn_skills_block_skipped_when_no_skills():
    """No skills attached → no per-turn [Skills] block (also no initial)."""
    orch = _build_orchestrator()
    request = ConversationRequest(
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
        skills=[],
        dynamic_system_prompt="Stay in character",
    )
    state: dict[str, Any] = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    state = orch._node_system_prompt(state)
    state = orch._node_user_input(state)
    skills_msgs = [m for m in state["messages"] if "<Skills>" in m["content"]]
    assert skills_msgs == [], "no <Skills> block when bot has no skills"


def test_per_turn_skills_block_positioned_between_reminder_and_world_state():
    """Per-turn ordering: [Reminder] → [Skills] → [World state from previous turn] → user.

    Skills sit between the dynamic prompt and the world state so the
    LLM reads them as a contiguous "behavioural rules" bundle at the
    end of the prompt — adjacent to the user turn and therefore
    surfaced by middle-out truncation that cuts the middle.
    """
    orch = _build_orchestrator()
    request = ConversationRequest(
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
        skills=[_make_skill(1, "Sarcastic", description="dry wit")],
        dynamic_system_prompt="Stay in character",
        prev_world_state="loc: tavern",
    )
    state: dict[str, Any] = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    state = orch._node_system_prompt(state)
    state = orch._node_user_input(state)
    messages = state["messages"]

    def _find_index(predicate):
        return next(i for i, m in enumerate(messages) if predicate(m["content"]))

    # Initial system-prompt block (early).
    initial_skills_idx = _find_index(lambda c: "<Skills>" in c)
    # Per-turn injections — look at indices AFTER history.
    reminder_idx = _find_index(lambda c: c.startswith("[Reminder] "))
    # Per-turn block is the SECOND <Skills> block (first is the initial).
    skills_indices = [
        i for i, m in enumerate(messages) if m["content"].startswith("<Skills>")
    ]
    per_turn_skills_idx = skills_indices[1]
    world_state_idx = _find_index(
        lambda c: c.startswith("[World state from previous turn] ")
    )
    user_idx = next(
        i for i, m in enumerate(messages) if m["role"] == "user"
    )

    # Initial block at idx 1 (after <Persona> at idx 0).
    assert initial_skills_idx == 1
    # Per-turn block lands between reminder and world state.
    assert reminder_idx < per_turn_skills_idx < world_state_idx, (
        f"expected reminder < per_turn_skills < world_state, "
        f"got reminder={reminder_idx} skills={per_turn_skills_idx} "
        f"world_state={world_state_idx}"
    )
    # And the user turn is the very last message.
    assert user_idx == len(messages) - 1


def test_per_turn_skills_block_positioned_after_reminder_only_when_no_world_state():
    """When prev_world_state is empty, the per-turn [Skills] block still
    lands after [Reminder] (or as the first per-turn injection when
    no reminder) and right before the user turn.
    """
    orch = _build_orchestrator()
    request = ConversationRequest(
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
        skills=[_make_skill(1, "Sarcastic", description="dry wit")],
        dynamic_system_prompt="Stay in character",
        prev_world_state="",
    )
    state: dict[str, Any] = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    state = orch._node_system_prompt(state)
    state = orch._node_user_input(state)
    messages = state["messages"]

    reminder_idx = next(
        i for i, m in enumerate(messages) if m["content"].startswith("[Reminder] ")
    )
    # Per-turn [Skills] is the second <Skills> block.
    skills_indices = [
        i for i, m in enumerate(messages) if m["content"].startswith("<Skills>")
    ]
    per_turn_skills_idx = skills_indices[1]
    user_idx = next(
        i for i, m in enumerate(messages) if m["role"] == "user"
    )
    assert reminder_idx < per_turn_skills_idx < user_idx


def test_per_turn_skills_block_when_no_reminder_only_skills():
    """When dynamic_system_prompt is empty but skills are present, the
    per-turn [Skills] block still fires. This guards against the
    'skills only fire when DSP is set' failure mode — Skills are an
    independent per-turn injection, not a sub-block of [Reminder].
    """
    orch = _build_orchestrator()
    request = ConversationRequest(
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
        skills=[_make_skill(1, "Sarcastic", description="dry wit")],
        dynamic_system_prompt="",  # empty — no reminder
        prev_world_state="",
    )
    state: dict[str, Any] = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    state = orch._node_system_prompt(state)
    state = orch._node_user_input(state)
    messages = state["messages"]

    skills_msgs = [m for m in messages if "<Skills>" in m["content"]]
    assert len(skills_msgs) == 2
    # No [Reminder] block.
    assert not any(
        m["content"].startswith("[Reminder] ") for m in messages
    ), "no reminder expected when DSP is empty"


def test_per_turn_skills_block_content_identical_to_initial():
    """The per-turn [Skills] block must render the same XML content
    as the initial [Skills] block — same format, same order, same
    skills. This is the safety-net invariant: the LLM sees the
    same rules regardless of which end of the prompt it attends to.
    """
    orch = _build_orchestrator()
    skills = [
        _make_skill(1, "Sarcastic", description="dry wit", instruction="apply when"),
        _make_skill(2, "Concise", description="short", instruction="keep brief"),
    ]
    request = ConversationRequest(
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
        skills=skills,
        dynamic_system_prompt="Stay in character",
    )

    # Graph path: initial block + per-turn block via _node_user_input.
    state: dict[str, Any] = {
        "request": request,
        "messages": [],
        "response": "",
        "bot_type": "rp",
    }
    state = orch._node_system_prompt(state)
    state = orch._node_user_input(state)
    graph_skills_msgs = [
        m["content"] for m in state["messages"]
        if m["role"] == "system" and "<Skills>" in m["content"]
    ]
    assert len(graph_skills_msgs) == 2
    assert graph_skills_msgs[0] == graph_skills_msgs[1], (
        "Initial and per-turn <Skills> blocks must have identical content"
    )

    # Streaming path: same identity check.
    stream_messages = orch._build_all_messages(request)
    stream_skills_msgs = [
        m["content"] for m in stream_messages
        if m["role"] == "system" and "<Skills>" in m["content"]
    ]
    assert len(stream_skills_msgs) == 2
    assert stream_skills_msgs[0] == stream_skills_msgs[1]
    # Cross-path: the per-turn block must be identical between graph
    # and streaming paths.
    assert graph_skills_msgs[1] == stream_skills_msgs[1], (
        "per-turn <Skills> block differs between graph and streaming paths"
    )


# ── _build_per_turn_injections helper (DRY regression guard) ─────
#
# Both prompt-assembly paths (``_node_user_input`` graph +
# ``_build_all_messages`` streaming) call this helper. A future
# edit that diverges the two paths would be a silent regression —
# these tests guard the helper directly so a refactor that
# accidentally drops or reorders an injection fails fast.


def test_per_turn_injections_helper_returns_three_blocks_when_all_present():
    """All three optional injections fire (in order) when DSP, skills,
    and prev_world_state are all non-empty.
    """
    orch = _build_orchestrator()
    request = ConversationRequest(
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
        skills=[_make_skill(1, "Sarcastic", description="dry wit")],
        dynamic_system_prompt="Stay in character",
        prev_world_state="loc: tavern",
    )
    injections = orch._build_per_turn_injections(request)
    assert len(injections) == 3
    assert injections[0]["content"].startswith("[Reminder] ")
    assert injections[0]["content"] == "[Reminder] Stay in character"
    assert injections[1]["content"].startswith("<Skills>")
    assert injections[2]["content"].startswith("[World state from previous turn] ")
    assert injections[2]["content"] == "[World state from previous turn] loc: tavern"


def test_per_turn_injections_helper_skips_empty_fields():
    """Empty DSP, empty skills, empty prev_world_state → empty list.
    Edge: when DSP is empty, [Reminder] is skipped; when skills is
    empty, [Skills] is skipped (per-turn AND initial — both go
    through _build_skills_block which returns None).
    """
    orch = _build_orchestrator()
    request = ConversationRequest(
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
        skills=[],
        dynamic_system_prompt="",
        prev_world_state="",
    )
    injections = orch._build_per_turn_injections(request)
    assert injections == []


def test_per_turn_injections_helper_preserves_order_with_subsets():
    """Subset of injections: ordering is preserved and skipped
    fields do NOT leave gaps. Specifically:
    - DSP only → [Reminder]
    - skills only → [Skills]
    - world_state only → [World state from previous turn]
    - DSP + skills (no world_state) → [Reminder, Skills]
    - DSP + world_state (no skills) → [Reminder, World state]
    - skills + world_state (no DSP) → [Skills, World state]
    """
    orch = _build_orchestrator()
    skills = [_make_skill(1, "Sarcastic", description="dry wit")]

    def _req(*, dsp="", skills_arg=None, world=""):
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
            skills=skills_arg if skills_arg is not None else [],
            dynamic_system_prompt=dsp,
            prev_world_state=world,
        )

    # DSP only.
    injections = orch._build_per_turn_injections(_req(dsp="Stay"))
    assert len(injections) == 1
    assert injections[0]["content"] == "[Reminder] Stay"

    # Skills only.
    injections = orch._build_per_turn_injections(_req(skills_arg=skills))
    assert len(injections) == 1
    assert injections[0]["content"].startswith("<Skills>")

    # World state only.
    injections = orch._build_per_turn_injections(_req(world="loc: tavern"))
    assert len(injections) == 1
    assert injections[0]["content"] == "[World state from previous turn] loc: tavern"

    # DSP + skills (no world_state).
    injections = orch._build_per_turn_injections(
        _req(dsp="Stay", skills_arg=skills)
    )
    assert len(injections) == 2
    assert injections[0]["content"] == "[Reminder] Stay"
    assert injections[1]["content"].startswith("<Skills>")

    # DSP + world_state (no skills).
    injections = orch._build_per_turn_injections(
        _req(dsp="Stay", world="loc: tavern")
    )
    assert len(injections) == 2
    assert injections[0]["content"] == "[Reminder] Stay"
    assert injections[1]["content"] == "[World state from previous turn] loc: tavern"

    # Skills + world_state (no DSP).
    injections = orch._build_per_turn_injections(
        _req(skills_arg=skills, world="loc: tavern")
    )
    assert len(injections) == 2
    assert injections[0]["content"].startswith("<Skills>")
    assert injections[1]["content"] == "[World state from previous turn] loc: tavern"


def test_per_turn_injections_helper_substitutes_variables_in_dsp():
    """DSP variable substitution (e.g. {{char}}) runs inside the helper.
    Confirms ``{{char}}`` is replaced with ``bot_name`` and the helper
    is the single point of substitution. We do NOT assert on
    ``{{user}}`` here because that placeholder requires a non-empty
    ``user_persona`` which would need an extra fake — out of scope
    for this DRY-guard test.
    """
    orch = _build_orchestrator()
    request = ConversationRequest(
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
        skills=[],
        dynamic_system_prompt="Always greet as {{char}}.",
        prev_world_state="",
    )
    injections = orch._build_per_turn_injections(request)
    assert len(injections) == 1
    assert injections[0]["content"].startswith("[Reminder] ")
    # {{char}} is substituted with bot_name.
    assert "{{char}}" not in injections[0]["content"]
    assert "Lili" in injections[0]["content"]
