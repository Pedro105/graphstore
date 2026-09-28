"""Chat import service: batch import of chat exports into the memory graph."""

import asyncio
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import structlog

from contextstore.core.service import remember
from contextstore.graph.store import GraphStore
from contextstore.imports.parsers import ParsedChat, ChatMessage, detect_and_parse
from contextstore.models.scope import Scope
from contextstore.vector.embeddings import EmbeddingProvider

logger = structlog.get_logger()


@dataclass
class ImportedMessage:
    """Result of importing a single message."""

    message_index: int
    role: str
    entities_extracted: int
    relations_extracted: int
    tokens_used: int


@dataclass
class ImportedConversation:
    """Result of importing a single conversation."""

    title: str
    messages_imported: int
    messages_skipped: int
    total_entities: int
    total_relations: int
    imported_messages: list[ImportedMessage] = field(default_factory=list)


@dataclass
class ImportResult:
    """Complete result of a chat import operation."""

    import_id: UUID
    source_format: str
    conversations_imported: int
    total_messages: int
    total_entities: int
    total_relations: int
    total_tokens: int
    conversations: list[ImportedConversation] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _format_message_for_extraction(
    msg: ChatMessage,
    conversation_title: str,
    msg_index: int,
    total_messages: int,
) -> str:
    """Format a chat message as content for the extraction pipeline.

    Provides context about the conversation and message position to help
    extraction understand relationships between entities mentioned.
    """
    role_label = "User" if msg.role == "user" else "Assistant"
    context = f'From conversation "{conversation_title}" ({role_label}, message {msg_index + 1}/{total_messages}):\n\n'
    return context + msg.content


async def import_chats(
    content: str | bytes,
    scope: Scope,
    graph_store: GraphStore,
    embedding_provider: EmbeddingProvider,
    source_prefix: str = "chat-import",
    skip_short_messages: int = 10,
    concurrency: int = 3,
) -> ImportResult:
    """Import chat exports into the memory graph.

    Parses the content (auto-detecting format), then feeds each message
    through the extraction pipeline. Messages from both user and assistant
    are processed, as both can contain factual claims about entities.

    Args:
        content: Raw chat export content (JSON or text).
        scope: Tenant scope for the imported memories.
        graph_store: Graph store instance.
        embedding_provider: Embedding provider instance.
        source_prefix: Prefix for the source field (conversation title appended).
        skip_short_messages: Skip messages shorter than this (character count).
        concurrency: Max concurrent extraction calls.

    Returns:
        ImportResult with counts and per-conversation breakdown.
    """
    import_id = uuid4()
    parsed = detect_and_parse(content)

    if not parsed:
        return ImportResult(
            import_id=import_id,
            source_format="unknown",
            conversations_imported=0,
            total_messages=0,
            total_entities=0,
            total_relations=0,
            total_tokens=0,
            errors=["No conversations found in the provided content."],
        )

    source_format = parsed[0].source_format if parsed else "unknown"
    result = ImportResult(
        import_id=import_id,
        source_format=source_format,
        conversations_imported=0,
        total_messages=0,
        total_entities=0,
        total_relations=0,
        total_tokens=0,
    )

    semaphore = asyncio.Semaphore(concurrency)

    async def process_message(
        msg: ChatMessage,
        conv: ParsedChat,
        msg_index: int,
    ) -> ImportedMessage | None:
        if len(msg.content.strip()) < skip_short_messages:
            return None

        if msg.role == "system":
            return None

        async with semaphore:
            try:
                formatted = _format_message_for_extraction(
                    msg, conv.title, msg_index, len(conv.messages)
                )
                source = f"{source_prefix}/{conv.title}"

                memory, tokens = await remember(
                    content=formatted,
                    scope=scope,
                    source=source,
                    graph_store=graph_store,
                    embedding_provider=embedding_provider,
                )

                return ImportedMessage(
                    message_index=msg_index,
                    role=msg.role,
                    entities_extracted=len(memory.entities),
                    relations_extracted=len(memory.relations),
                    tokens_used=tokens,
                )
            except Exception as e:
                logger.exception(
                    "import.message_failed",
                    conversation=conv.title,
                    message_index=msg_index,
                    error=str(e),
                )
                result.errors.append(
                    f"Failed to import message {msg_index + 1} from '{conv.title}': {e}"
                )
                return None

    for conv in parsed:
        conv_result = ImportedConversation(
            title=conv.title,
            messages_imported=0,
            messages_skipped=0,
            total_entities=0,
            total_relations=0,
        )

        tasks = [
            process_message(msg, conv, i) for i, msg in enumerate(conv.messages)
        ]
        imported = await asyncio.gather(*tasks)

        for msg_result in imported:
            if msg_result is None:
                conv_result.messages_skipped += 1
            else:
                conv_result.messages_imported += 1
                conv_result.total_entities += msg_result.entities_extracted
                conv_result.total_relations += msg_result.relations_extracted
                conv_result.imported_messages.append(msg_result)
                result.total_tokens += msg_result.tokens_used

        if conv_result.messages_imported > 0:
            result.conversations_imported += 1
            result.total_messages += conv_result.messages_imported
            result.total_entities += conv_result.total_entities
            result.total_relations += conv_result.total_relations
            result.conversations.append(conv_result)

    logger.info(
        "import.completed",
        import_id=str(import_id),
        source_format=source_format,
        conversations=result.conversations_imported,
        messages=result.total_messages,
        entities=result.total_entities,
        relations=result.total_relations,
    )

    return result
