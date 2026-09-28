"""Chat export parsers: ChatGPT JSON, Claude JSON, and generic markdown/text."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ChatMessage:
    """A single message extracted from a chat export."""

    role: str
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedChat:
    """A parsed conversation with its messages and metadata."""

    title: str
    messages: list[ChatMessage]
    source_format: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _safe_timestamp(ts: float | int | str | None) -> datetime | None:
    """Convert various timestamp formats to datetime, or None if invalid."""
    if ts is None:
        return None
    try:
        if isinstance(ts, str):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromtimestamp(float(ts))
    except (ValueError, TypeError, OSError):
        return None


def parse_chatgpt_export(data: dict[str, Any] | list[dict[str, Any]]) -> list[ParsedChat]:
    """Parse ChatGPT export JSON (conversations.json format).

    ChatGPT exports have this structure:
    [
      {
        "title": "Conversation Title",
        "create_time": 1234567890.123,
        "mapping": {
          "uuid1": {
            "message": {
              "author": {"role": "user"|"assistant"|"system"},
              "content": {"parts": ["text content"]},
              "create_time": 1234567890.123
            },
            "parent": "uuid0"|null,
            "children": ["uuid2"]
          },
          ...
        }
      },
      ...
    ]
    """
    if isinstance(data, dict):
        conversations = [data]
    else:
        conversations = data

    results: list[ParsedChat] = []

    for conv in conversations:
        title = conv.get("title", "Untitled Conversation")
        mapping = conv.get("mapping", {})

        messages: list[ChatMessage] = []
        ordered_nodes: list[tuple[float, dict[str, Any]]] = []

        for node_id, node in mapping.items():
            msg = node.get("message")
            if not msg:
                continue
            author = msg.get("author", {})
            role = author.get("role", "unknown")
            if role == "system":
                continue

            content_obj = msg.get("content", {})
            parts = content_obj.get("parts", [])
            if not parts:
                continue

            content = "\n".join(str(p) for p in parts if p)
            if not content.strip():
                continue

            create_time = msg.get("create_time", 0) or 0
            ordered_nodes.append((
                create_time,
                {"role": role, "content": content, "timestamp": _safe_timestamp(create_time)},
            ))

        ordered_nodes.sort(key=lambda x: x[0])
        messages = [
            ChatMessage(
                role=node["role"],
                content=node["content"],
                timestamp=node["timestamp"],
            )
            for _, node in ordered_nodes
        ]

        if messages:
            results.append(ParsedChat(
                title=title,
                messages=messages,
                source_format="chatgpt",
                metadata={"create_time": _safe_timestamp(conv.get("create_time"))},
            ))

    return results


def parse_claude_export(data: dict[str, Any] | list[dict[str, Any]]) -> list[ParsedChat]:
    """Parse Claude export JSON.

    Claude exports can vary but commonly have:
    {
      "name": "Conversation Name",
      "chat_messages": [
        {"sender": "human"|"assistant", "text": "content", "created_at": "..."}
      ]
    }
    or a list of such conversations.
    """
    if isinstance(data, dict):
        if "chat_messages" in data:
            conversations = [data]
        elif isinstance(data.get("conversations"), list):
            conversations = data["conversations"]
        else:
            conversations = [data]
    else:
        conversations = data

    results: list[ParsedChat] = []

    for conv in conversations:
        title = conv.get("name") or conv.get("title") or "Untitled Conversation"
        chat_messages = conv.get("chat_messages", [])

        messages: list[ChatMessage] = []
        for msg in chat_messages:
            sender = msg.get("sender", "unknown")
            role = "user" if sender == "human" else "assistant" if sender == "assistant" else sender
            text = msg.get("text", "")
            if not text.strip():
                continue

            timestamp = _safe_timestamp(msg.get("created_at") or msg.get("timestamp"))
            messages.append(ChatMessage(role=role, content=text, timestamp=timestamp))

        if messages:
            results.append(ParsedChat(
                title=title,
                messages=messages,
                source_format="claude",
                metadata={"uuid": conv.get("uuid")},
            ))

    return results


_ROLE_PATTERNS = [
    (re.compile(r"^(?:User|Human|Me):\s*", re.IGNORECASE), "user"),
    (re.compile(r"^(?:Assistant|AI|Claude|ChatGPT|GPT|Bot):\s*", re.IGNORECASE), "assistant"),
    (re.compile(r"^(?:System):\s*", re.IGNORECASE), "system"),
]

_HEADER_PATTERN = re.compile(
    r"^#+\s+(.+)|^---+$|^={3,}$|^\*{3,}$", re.MULTILINE
)


def parse_markdown_transcript(text: str) -> list[ParsedChat]:
    """Parse a markdown or plain text chat transcript.

    Supports formats like:
    - "User: message" / "Assistant: message" style
    - Messages separated by blank lines
    - Markdown headers as conversation separators
    """
    if not text.strip():
        return []

    conversations: list[ParsedChat] = []
    current_title = "Imported Transcript"
    current_messages: list[ChatMessage] = []
    current_role = "user"
    current_content: list[str] = []

    def flush_message():
        nonlocal current_content, current_role
        content = "\n".join(current_content).strip()
        if content:
            current_messages.append(ChatMessage(role=current_role, content=content))
        current_content = []

    def flush_conversation():
        nonlocal current_messages, current_title
        flush_message()
        if current_messages:
            conversations.append(ParsedChat(
                title=current_title,
                messages=current_messages,
                source_format="markdown",
            ))
        current_messages = []
        current_title = "Imported Transcript"

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if _HEADER_PATTERN.match(stripped):
            flush_conversation()
            match = re.match(r"^#+\s+(.+)", stripped)
            if match:
                current_title = match.group(1).strip()
            i += 1
            continue

        matched_role = None
        for pattern, role in _ROLE_PATTERNS:
            match = pattern.match(stripped)
            if match:
                matched_role = role
                stripped = stripped[match.end():].strip()
                break

        if matched_role:
            flush_message()
            current_role = matched_role
            if stripped:
                current_content.append(stripped)
        elif stripped:
            current_content.append(stripped)
        elif current_content:
            flush_message()
            current_role = "assistant" if current_role == "user" else "user"

        i += 1

    flush_conversation()
    return conversations if conversations else []


def detect_and_parse(content: str | bytes) -> list[ParsedChat]:
    """Auto-detect format and parse chat export.

    Tries JSON parsing first (ChatGPT/Claude), falls back to markdown.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    content = content.strip()
    if not content:
        return []

    if content.startswith(("{", "[")):
        try:
            data = json.loads(content)
            if isinstance(data, list) and data:
                sample = data[0]
            elif isinstance(data, dict):
                sample = data
            else:
                return parse_markdown_transcript(content)

            if "mapping" in sample:
                return parse_chatgpt_export(data)
            if "chat_messages" in sample or (
                isinstance(data, dict) and "conversations" in data
            ):
                return parse_claude_export(data)

            if isinstance(data, list) and all(
                isinstance(item, dict) and "mapping" in item for item in data
            ):
                return parse_chatgpt_export(data)

            return parse_markdown_transcript(content)
        except json.JSONDecodeError:
            pass

    return parse_markdown_transcript(content)
