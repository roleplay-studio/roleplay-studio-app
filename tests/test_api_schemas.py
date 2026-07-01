"""Tests for Pydantic API schemas — mes_example field on bot models.

These tests lock in:
  - BotResponse includes mes_example in serialized output
  - CreateBotCommand and UpdateBotCommand accept mes_example
  - UpdateBotRequest.mes_example can be None (skip) or str (update)
  - Pydantic round-trip: model_dump() includes the field
"""

from __future__ import annotations

from api.schemas import UpdateBotRequest
from app.application.dto import BotResponse, CreateBotCommand, UpdateBotCommand


class TestBotResponseMesExample:
    """BotResponse (the API response model) includes mes_example."""

    def test_bot_read_includes_mes_example(self) -> None:
        bot = BotResponse(id=1, name="X", personality="p", mes_example="<START>...\n<END>")
        assert bot.mes_example == "<START>...\n<END>"

    def test_bot_read_default_mes_example_empty(self) -> None:
        bot = BotResponse(id=1, name="X", personality="p")
        assert bot.mes_example == ""

    def test_bot_read_model_dump_includes_mes_example(self) -> None:
        bot = BotResponse(id=1, name="X", personality="p", mes_example="value")
        dumped = bot.model_dump()
        assert "mes_example" in dumped
        assert dumped["mes_example"] == "value"


class TestCreateBotCommandMesExample:
    """CreateBotCommand (used for bot creation) accepts mes_example."""

    def test_create_bot_command_default_mes_example_empty(self) -> None:
        cmd = CreateBotCommand(name="X", personality="p", first_message="f")
        assert cmd.mes_example == ""

    def test_create_bot_command_accepts_mes_example(self) -> None:
        cmd = CreateBotCommand(
            name="X", personality="p", first_message="f", mes_example="<START>...\n<END>"
        )
        assert cmd.mes_example == "<START>...\n<END>"


class TestUpdateBotCommandMesExample:
    """UpdateBotCommand (used for bot updates) accepts mes_example."""

    def test_update_bot_command_default_mes_example_empty(self) -> None:
        cmd = UpdateBotCommand(bot_id=1, name="X", personality="p", first_message="f")
        assert cmd.mes_example == ""


class TestUpdateBotRequestMesExample:
    """UpdateBotRequest (the API request model) accepts optional mes_example."""

    def test_update_bot_request_mes_example_none_skips_field(self) -> None:
        req = UpdateBotRequest(name="X", personality="p", first_message="f", mes_example=None)
        assert req.mes_example is None

    def test_update_bot_request_mes_example_str_updates_field(self) -> None:
        req = UpdateBotRequest(
            name="X",
            personality="p",
            first_message="f",
            mes_example="new dialogue",
        )
        assert req.mes_example == "new dialogue"

    def test_update_bot_request_mes_example_default_none(self) -> None:
        req = UpdateBotRequest(name="X", personality="p", first_message="f")
        assert req.mes_example is None

    def test_update_bot_request_multiline_mes_example_preserved(self) -> None:
        multiline = "<START>\n{{user}}: hi\n{{char}}: hello\n<END>"
        req = UpdateBotRequest(name="X", personality="p", first_message="f", mes_example=multiline)
        assert req.mes_example == multiline
