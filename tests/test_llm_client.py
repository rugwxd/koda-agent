"""Tests for LLM models and conversation management."""

import pytest

from src.llm.models import (
    Conversation,
    LLMResponse,
    Message,
    Role,
    TextContent,
    ToolDefinition,
    ToolResultContent,
    ToolUseContent,
)


class TestMessage:
    def test_text_message(self):
        msg = Message(role=Role.USER, content=[TextContent(text="hello")])
        assert msg.text == "hello"
        assert msg.tool_calls == []

    def test_tool_use_message(self):
        msg = Message(
            role=Role.ASSISTANT,
            content=[
                TextContent(text="Let me read that"),
                ToolUseContent(id="tc_1", name="read_file", input={"path": "foo.py"}),
            ],
        )
        assert msg.text == "Let me read that"
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "read_file"

    def test_to_api_format(self):
        msg = Message(role=Role.USER, content=[TextContent(text="hi")])
        fmt = msg.to_api_format()
        assert fmt["role"] == "user"
        assert fmt["content"][0]["type"] == "text"
        assert fmt["content"][0]["text"] == "hi"


class TestConversation:
    def test_add_messages(self):
        conv = Conversation(system_prompt="You are helpful")
        conv.add_user_message("hello")
        assert len(conv.messages) == 1
        assert conv.messages[0].role == Role.USER

    def test_add_tool_results(self):
        conv = Conversation()
        conv.add_user_message("do something")
        conv.add_assistant_message([
            ToolUseContent(id="tc_1", name="read", input={"path": "x"}),
        ])
        conv.add_tool_results([
            ToolResultContent(tool_use_id="tc_1", content="file contents"),
        ])
        assert len(conv.messages) == 3
        assert conv.messages[2].role == Role.USER

    def test_to_api_format(self):
        conv = Conversation(system_prompt="system")
        conv.add_user_message("hello")
        api_msgs = conv.to_api_format()
        assert len(api_msgs) == 1
        assert api_msgs[0]["role"] == "user"

    def test_token_estimate(self):
        conv = Conversation(system_prompt="A" * 400)
        conv.add_user_message("B" * 400)
        # 800 chars / 4 = 200 tokens
        assert conv.token_estimate == 200


class TestLLMResponse:
    def test_text_response(self):
        resp = LLMResponse(
            content=[TextContent(text="Done!")],
            stop_reason="end_turn",
            model="test",
            input_tokens=100,
            output_tokens=50,
        )
        assert resp.text == "Done!"
        assert not resp.has_tool_calls
        assert resp.total_tokens == 150

    def test_tool_use_response(self):
        resp = LLMResponse(
            content=[
                TextContent(text="Reading file"),
                ToolUseContent(id="tc_1", name="read_file", input={"path": "x.py"}),
            ],
            stop_reason="tool_use",
            model="test",
            input_tokens=200,
            output_tokens=100,
        )
        assert resp.has_tool_calls
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "read_file"


class TestToolDefinition:
    def test_to_api_format(self):
        td = ToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
        )
        fmt = td.to_api_format()
        assert fmt["name"] == "test_tool"
        assert "properties" in fmt["input_schema"]
