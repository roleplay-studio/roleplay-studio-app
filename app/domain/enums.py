"""Domain enums for Roleplay Studio."""

from __future__ import annotations

from enum import StrEnum


class BotType(StrEnum):
    """Type of a bot — determines conversation prompt structure and UI."""

    RP = "rp"
    ASSISTANT = "assistant"
    AGENT = "agent"

    @property
    def label(self) -> str:
        labels = {
            BotType.RP: "🎭 RolePlay",
            BotType.ASSISTANT: "🤖 Assistant",
            BotType.AGENT: "🛠️ Agent",
        }
        return labels[self]

    @property
    def description(self) -> str:
        descs = {
            BotType.RP: "Character with personality, scenario, first message",
            BotType.ASSISTANT: "Helpful AI with system prompt",
            BotType.AGENT: "AI agent with file upload & tools",
        }
        return descs[self]
