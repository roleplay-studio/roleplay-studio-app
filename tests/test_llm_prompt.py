"""Tests for LLM prompt consistency — validates that the full LLM
message sequence (system + history + user input) is correctly structured
after various chat operations using the real LangGraph orchestrator."""

import importlib.util
import sys

from app.application.dto import SendMessageCommand
from app.application.services import ChatService
from app.infrastructure.orchestration.langgraph_orchestrator import (
    LangGraphConversationOrchestrator,
)

sys.path.insert(0, "tests")
spec = importlib.util.spec_from_file_location(
    "test_chat_generation", "tests/test_chat_generation.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

FakeBotRepo = mod.FakeBotRepo
FakeLLM = mod.FakeLLM
FakeKnowledgeRepo = mod.FakeKnowledgeRepo
FakeOrchestrator = mod.FakeOrchestrator
BranchMessageRepo = mod.BranchMessageRepo
_make_bot = mod._make_bot
_make_bot_with_mes_example = mod._make_bot_with_mes_example
check_dialogue_consistency = mod.check_dialogue_consistency
check_llm_prompt_consistency = mod.check_llm_prompt_consistency


class TestLlmPromptConsistency:
    """Validate the full LLM message sequence (system + history + user input)
    using the real LangGraph orchestrator."""

    async def test_system_prompt_includes_personality_and_scenario(self):
        """System message should contain personality and scenario."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        bots._bots[bot_id]["personality"] = "Friendly catgirl"
        bots._bots[bot_id]["scenario"] = "Cozy cafe in Neo-Tokyo"

        msgs = BranchMessageRepo()
        llm = FakeLLM(response="Welcome!")
        orch = LangGraphConversationOrchestrator(llm)
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        async for _ in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
        ):
            pass

        prompt_issues = check_llm_prompt_consistency(
            llm.last_messages,
            bot_personality="Friendly catgirl",
            bot_scenario="Cozy cafe in Neo-Tokyo",
            bot_first_message="Hello!",
        )
        assert not prompt_issues, "\n".join(prompt_issues)

        # Verify specific tags
        system = llm.last_messages[0]["content"]
        assert "<Persona>" in system
        assert "Friendly catgirl" in system
        assert "<Scenario>" in system
        assert "Cozy cafe in Neo-Tokyo" in system

    async def test_system_prompt_includes_user_persona(self):
        """When user persona is set, it appears in the system prompt."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        bots._bots[bot_id]["personality"] = "Wise wizard"
        bots._bots[bot_id]["scenario"] = "Ancient library"

        from app.application.dto import UserPersonaDTO

        class PersonaRepo:
            async def get(self, persona_id):
                return UserPersonaDTO(id=1, name="Merlin", description="A powerful wizard")

            async def list(self):
                return []

        msgs = BranchMessageRepo()
        llm = FakeLLM(response="Greetings!")
        orch = LangGraphConversationOrchestrator(llm)
        service = ChatService(
            bots,
            msgs,
            FakeKnowledgeRepo(),
            orch,
            personas=PersonaRepo(),
        )

        async for _ in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hello", persona_id=1)
        ):
            pass

        prompt_issues = check_llm_prompt_consistency(
            llm.last_messages,
            bot_personality="Wise wizard",
            bot_scenario="Ancient library",
            user_persona_name="Merlin",
            bot_first_message="Hello!",
        )
        assert not prompt_issues, "\n".join(prompt_issues)

        system = llm.last_messages[0]["content"]
        assert "Merlin" in system
        assert "<UserPersona>" in system

    async def test_llm_sequence_after_full_conversation(self):
        """Full conversation: system, then user/assistant alternation."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello there!")
        bots._bots[bot_id]["personality"] = "Cheerful guide"
        bots._bots[bot_id]["scenario"] = "Fantasy world"

        msgs = BranchMessageRepo()
        llm = FakeLLM()
        orch = LangGraphConversationOrchestrator(llm)
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        exchanges = [
            ("Hi!", "Welcome adventurer!"),
            ("Tell me about this place", "This is Eldoria..."),
        ]
        for user_msg, asst_resp in exchanges:
            llm._response = asst_resp
            async for _ in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input=user_msg)
            ):
                pass

        prompt_issues = check_llm_prompt_consistency(
            llm.last_messages,
            bot_personality="Cheerful guide",
            bot_scenario="Fantasy world",
            bot_first_message="Hello there!",
        )
        assert not prompt_issues, "\n".join(prompt_issues)

        # First message is always system
        assert llm.last_messages[0]["role"] == "system"

        prompt_issues2 = check_llm_prompt_consistency(
            llm.last_messages,
            bot_personality="Cheerful guide",
            bot_scenario="Fantasy world",
            bot_first_message="Hello there!",
        )
        assert not prompt_issues2, "\n".join(prompt_issues2)

        # Stored messages should also be consistent
        stored = await msgs.list_all_for_thread(1)
        dialogue_issues = check_dialogue_consistency(
            stored,
            bot_first_message="Hello there!",
        )
        assert not dialogue_issues, "\n".join(dialogue_issues)

    async def test_llm_sequence_after_regen(self):
        """After regeneration, LLM prompt should still be valid."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        bots._bots[bot_id]["personality"] = "Helpful bot"
        bots._bots[bot_id]["scenario"] = "Tech support"

        msgs = BranchMessageRepo()
        llm = FakeLLM()
        orch = LangGraphConversationOrchestrator(llm)
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        llm._response = "How can I help?"
        async for _ in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="I have a problem")
        ):
            pass

        llm._response = "Let me check that!"
        async for _ in service.regenerate_message(1, 3, bot_id):
            pass

        prompt_issues = check_llm_prompt_consistency(
            llm.last_messages,
            bot_personality="Helpful bot",
            bot_scenario="Tech support",
            bot_first_message="Hello!",
        )
        assert not prompt_issues, "\n".join(prompt_issues)

        # Stored dialogue should also be consistent
        stored = await msgs.list_all_for_thread(1)
        dialogue_issues = check_dialogue_consistency(
            stored,
            bot_first_message="Hello!",
        )
        assert not dialogue_issues, "\n".join(dialogue_issues)


# ── mes_example injection (V1/V2/V3 few-shot examples) ────────────


class TestMesExampleInjection:
    """Verify the orchestrator injects mes_example as a system message
    between the main system prompt and the first user-visible message,
    and skips injection when mes_example is empty."""

    async def test_no_mes_example_no_examples_system_message(self):
        """When mes_example is empty, no '### Example Dialogues' block is injected."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        llm = FakeLLM(response="Hello!")
        orch = LangGraphConversationOrchestrator(llm)
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        async for _ in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
        ):
            pass

        example_messages = [
            m
            for m in llm.last_messages
            if m["role"] == "system" and "Example Dialogues" in m["content"]
        ]
        assert example_messages == []

    async def test_mes_example_injects_one_system_message(self):
        """When mes_example is non-empty, exactly one system message with the
        '### Example Dialogues' header is injected."""
        bots = FakeBotRepo()
        examples = "<START>\n{{user}}: hi\n{{char}}: hello\n<END>"
        bot_id = await _make_bot_with_mes_example(bots, examples)
        msgs = BranchMessageRepo()
        llm = FakeLLM(response="Hi!")
        orch = LangGraphConversationOrchestrator(llm)
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        async for _ in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
        ):
            pass

        example_messages = [
            m
            for m in llm.last_messages
            if m["role"] == "system" and "Example Dialogues" in m["content"]
        ]
        assert len(example_messages) == 1
        assert "<START>" in example_messages[0]["content"]
        assert "These are sample exchanges" in example_messages[0]["content"]

    async def test_mes_example_positioned_between_main_system_and_first_message(self):
        """The examples system message is between the main system message
        (index 0) and the first_message (next assistant role)."""
        bots = FakeBotRepo()
        examples = "<START>\n{{user}}: a\n<END>"
        bot_id = await _make_bot_with_mes_example(
            bots, examples, first_message="Welcome to the cafe!"
        )
        msgs = BranchMessageRepo()
        llm = FakeLLM(response="Hi!")
        orch = LangGraphConversationOrchestrator(llm)
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        async for _ in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
        ):
            pass

        # Find the indices
        example_idx = None
        first_message_idx = None
        for i, m in enumerate(llm.last_messages):
            if m["role"] == "system" and "Example Dialogues" in m["content"]:
                example_idx = i
            if m["role"] == "assistant" and m["content"] == "Welcome to the cafe!":
                first_message_idx = i

        assert example_idx is not None, "Example Dialogues message not found"
        assert first_message_idx is not None, "first_message not found"
        assert example_idx < first_message_idx, (
            f"Example Dialogues (idx {example_idx}) must come before "
            f"first_message (idx {first_message_idx})"
        )
        # And the main system message is at index 0
        assert llm.last_messages[0]["role"] == "system"
        assert "Example Dialogues" not in llm.last_messages[0]["content"]

    async def test_mes_example_substitutes_placeholders(self):
        """``{{user}}`` and ``{{char}}`` in mes_example must be
        replaced with the user persona name and bot name before the
        block is sent to the LLM. Otherwise the model sometimes
        echoes the literal tokens back into the live reply.
        """
        from app.application.dto import UserPersonaDTO

        class PersonaRepo:
            async def get(self, persona_id):
                return UserPersonaDTO(id=1, name="Merlin", description="A wizard")

            async def list(self):
                return []

        bots = FakeBotRepo()
        examples = "<START>\n{{user}}: greetings\n{{char}}: well met, traveller\n<END>"
        bot_id = await _make_bot_with_mes_example(bots, examples)

        msgs = BranchMessageRepo()
        llm = FakeLLM(response="Hi!")
        orch = LangGraphConversationOrchestrator(llm)
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch, personas=PersonaRepo())

        async for _ in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi", persona_id=1)
        ):
            pass

        example_messages = [
            m
            for m in llm.last_messages
            if m["role"] == "system" and "Example Dialogues" in m["content"]
        ]
        assert len(example_messages) == 1
        body = example_messages[0]["content"]
        # Placeholders substituted — no raw tokens leak into the prompt.
        assert "{{user}}" not in body, f"{{{{user}}}} leaked into prompt: {body!r}"
        assert "{{char}}" not in body, f"{{{{char}}}} leaked into prompt: {body!r}"
        # Substituted with the persona name + bot name (FakeBotRepo
        # creates a bot named "Kira").
        assert "Merlin" in body
        assert "Kira" in body
        # Original turn text still present.
        assert "greetings" in body
        assert "well met, traveller" in body
