import logging

from app.application.dto import ConversationSummary, MessageDTO
from app.application.ports import LLMPort

logger = logging.getLogger(__name__)


class SummaryService:
    def __init__(self, llm: LLMPort):
        self._llm = llm

    async def summarize(self, conversation_history: list[MessageDTO]) -> ConversationSummary:
        if not conversation_history:
            return ConversationSummary(content="No conversation to summarize.")

        history_text = "\n".join(
            f"{message.role}: {message.content}" for message in conversation_history
        )
        messages = [
            {
                "role": "system",
                "content": "You are a summarization assistant. Summarize the conversation concisely.",
            },
            {"role": "user", "content": f"Conversation:\n{history_text}\n\nSummary:"},
        ]
        content = await self._llm.generate_response(messages)
        return ConversationSummary(content=content)
