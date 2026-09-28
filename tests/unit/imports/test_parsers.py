"""Tests for chat export parsers."""

import json

import pytest

from contextstore.imports.parsers import (
    parse_chatgpt_export,
    parse_claude_export,
    parse_markdown_transcript,
    detect_and_parse,
)


class TestChatGPTParser:
    def test_parses_single_conversation(self):
        data = {
            "title": "Test Chat",
            "create_time": 1695312000,
            "mapping": {
                "msg-1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["Hello"]},
                        "create_time": 1695312001,
                    },
                    "parent": None,
                    "children": ["msg-2"],
                },
                "msg-2": {
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {"parts": ["Hi there!"]},
                        "create_time": 1695312002,
                    },
                    "parent": "msg-1",
                    "children": [],
                },
            },
        }

        result = parse_chatgpt_export(data)

        assert len(result) == 1
        assert result[0].title == "Test Chat"
        assert result[0].source_format == "chatgpt"
        assert len(result[0].messages) == 2
        assert result[0].messages[0].role == "user"
        assert result[0].messages[0].content == "Hello"
        assert result[0].messages[1].role == "assistant"

    def test_parses_multiple_conversations(self):
        data = [
            {
                "title": "Chat 1",
                "create_time": 1695312000,
                "mapping": {
                    "msg-1": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": ["First chat"]},
                            "create_time": 1695312001,
                        },
                        "parent": None,
                        "children": [],
                    },
                },
            },
            {
                "title": "Chat 2",
                "create_time": 1695398400,
                "mapping": {
                    "msg-1": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": ["Second chat"]},
                            "create_time": 1695398401,
                        },
                        "parent": None,
                        "children": [],
                    },
                },
            },
        ]

        result = parse_chatgpt_export(data)

        assert len(result) == 2
        assert result[0].title == "Chat 1"
        assert result[1].title == "Chat 2"

    def test_skips_system_messages(self):
        data = {
            "title": "Test",
            "create_time": 1695312000,
            "mapping": {
                "msg-1": {
                    "message": {
                        "author": {"role": "system"},
                        "content": {"parts": ["You are an assistant"]},
                        "create_time": 1695312001,
                    },
                    "parent": None,
                    "children": ["msg-2"],
                },
                "msg-2": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["Hello"]},
                        "create_time": 1695312002,
                    },
                    "parent": "msg-1",
                    "children": [],
                },
            },
        }

        result = parse_chatgpt_export(data)
        assert len(result[0].messages) == 1
        assert result[0].messages[0].role == "user"

    def test_orders_messages_by_timestamp(self):
        data = {
            "title": "Test",
            "create_time": 1695312000,
            "mapping": {
                "msg-later": {
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {"parts": ["Second"]},
                        "create_time": 1695312010,
                    },
                    "parent": None,
                    "children": [],
                },
                "msg-earlier": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["First"]},
                        "create_time": 1695312001,
                    },
                    "parent": None,
                    "children": [],
                },
            },
        }

        result = parse_chatgpt_export(data)
        assert result[0].messages[0].content == "First"
        assert result[0].messages[1].content == "Second"


class TestClaudeParser:
    def test_parses_single_conversation(self):
        data = {
            "name": "Test Conversation",
            "chat_messages": [
                {"sender": "human", "text": "Hello Claude"},
                {"sender": "assistant", "text": "Hello! How can I help?"},
            ],
        }

        result = parse_claude_export(data)

        assert len(result) == 1
        assert result[0].title == "Test Conversation"
        assert result[0].source_format == "claude"
        assert len(result[0].messages) == 2
        assert result[0].messages[0].role == "user"
        assert result[0].messages[1].role == "assistant"

    def test_parses_list_of_conversations(self):
        data = [
            {"name": "Chat 1", "chat_messages": [{"sender": "human", "text": "Hi"}]},
            {"name": "Chat 2", "chat_messages": [{"sender": "human", "text": "Hey"}]},
        ]

        result = parse_claude_export(data)
        assert len(result) == 2

    def test_parses_conversations_wrapper(self):
        data = {
            "conversations": [
                {"name": "Nested Chat", "chat_messages": [{"sender": "human", "text": "Hello"}]},
            ],
        }

        result = parse_claude_export(data)
        assert len(result) == 1
        assert result[0].title == "Nested Chat"


class TestMarkdownParser:
    def test_parses_basic_transcript(self):
        text = "User: Hello there\n\nBot: Hi! How can I help?"

        result = parse_markdown_transcript(text)

        assert len(result) == 1
        assert len(result[0].messages) == 2
        assert result[0].messages[0].role == "user"
        assert result[0].messages[0].content == "Hello there"
        assert result[0].messages[1].role == "assistant"

    def test_parses_human_assistant_format(self):
        text = "Human: What is the capital of France?\n\nAssistant: The capital of France is Paris."

        result = parse_markdown_transcript(text)

        assert len(result[0].messages) == 2
        assert result[0].messages[0].role == "user"
        assert result[0].messages[1].role == "assistant"
        assert "Paris" in result[0].messages[1].content

    def test_parses_headers_as_conversation_separators(self):
        text = "# Chat 1\n\nUser: Hello\n\n# Chat 2\n\nUser: World"

        result = parse_markdown_transcript(text)

        assert len(result) == 2
        assert result[0].title == "Chat 1"
        assert result[1].title == "Chat 2"

    def test_returns_empty_for_empty_input(self):
        result = parse_markdown_transcript("")
        assert result == []

        result = parse_markdown_transcript("   \n\n   ")
        assert result == []


class TestDetectAndParse:
    def test_detects_chatgpt_format(self):
        data = [
            {
                "title": "Test",
                "create_time": 1695312000,
                "mapping": {
                    "msg-1": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": ["Hello"]},
                            "create_time": 1695312001,
                        },
                        "parent": None,
                        "children": [],
                    },
                },
            }
        ]

        result = detect_and_parse(json.dumps(data))
        assert len(result) == 1
        assert result[0].source_format == "chatgpt"

    def test_detects_claude_format(self):
        data = {"name": "Test", "chat_messages": [{"sender": "human", "text": "Hi"}]}

        result = detect_and_parse(json.dumps(data))
        assert len(result) == 1
        assert result[0].source_format == "claude"

    def test_falls_back_to_markdown(self):
        text = "User: Hello\n\nBot: Hi there!"

        result = detect_and_parse(text)
        assert len(result) == 1
        assert result[0].source_format == "markdown"

    def test_handles_bytes_input(self):
        text = b"User: Hello\n\nBot: Hi!"

        result = detect_and_parse(text)
        assert len(result) == 1

    def test_returns_empty_for_empty_input(self):
        result = detect_and_parse("")
        assert result == []

        result = detect_and_parse(b"")
        assert result == []
