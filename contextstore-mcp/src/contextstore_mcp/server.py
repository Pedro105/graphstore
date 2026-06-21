"""MCP server exposing ContextStore's remember/recall as tools.

Tool docstrings below are read by the calling agent to decide when and how
to use these tools -- they're written for that audience, not just as
internal documentation.
"""

from mcp.server.fastmcp import FastMCP

from contextstore_mcp.client import ContextStoreClient
from contextstore_mcp.config import get_mcp_settings
from contextstore_mcp.models import RecallResult, RememberResult

settings = get_mcp_settings()
# The API key is sent as a Bearer token on every call; the backend resolves the
# tenant from it, so this server never constructs or sends a tenant_id/scope.
client = ContextStoreClient(base_url=settings.api_url, api_key=settings.api_key)

mcp = FastMCP("contextstore")


def _format_remember_result(memory: RememberResult) -> str:
    if not memory.entities:
        return "Stored, but no entities were extracted from this content."
    entity_summary = ", ".join(f"{e.name} ({e.entity_type})" for e in memory.entities)
    return f"Stored. Extracted entities: {entity_summary}."


def _format_recall_result(result: RecallResult) -> str:
    # Prefer the synthesised prose answer when synthesis ran and succeeded --
    # that's what a calling agent actually wants, rather than a structured blob
    # it has to interpret itself. Fall back to the structured summary below when
    # synthesis was skipped or failed (result.synthesis is None).
    if result.synthesis is not None:
        answer = result.synthesis.answer
        if result.synthesis.caveat:
            answer += f"\n\n(Caveat: {result.synthesis.caveat})"
        return answer

    if not result.entities:
        return "No relevant memories found."

    entities_by_id = {entity.id: entity for entity in result.entities}
    lines = ["Entities:"]
    lines.extend(f"- {entity.name} ({entity.entity_type})" for entity in result.entities)

    if result.relations:
        lines.append("")
        lines.append("Relations:")
        for relation in result.relations:
            source = entities_by_id.get(relation.source_entity_id)
            target = entities_by_id.get(relation.target_entity_id)
            source_name = source.name if source else str(relation.source_entity_id)
            target_name = target.name if target else str(relation.target_entity_id)
            lines.append(
                f"- {source_name} --[{relation.relation_type}]--> {target_name} "
                f"(confidence: {relation.provenance.confidence:.2f}, "
                f"source: {relation.provenance.source})"
            )

    return "\n".join(lines)


@mcp.tool()
async def contextstore_remember(content: str, extra_scope: dict[str, str] | None = None) -> str:
    """Store a fact, decision, or observation in long-term memory for later recall.

    Use this for information worth persisting beyond the current
    conversation: stated facts about people, projects, or organizations;
    decisions that were made and why; or observations about how something
    works. Do NOT use this for transient conversational content
    (greetings, clarifying questions, acknowledgments) or for things that
    are only true momentarily and not worth looking up again later.

    Write `content` as a natural-language statement of fact, not
    pre-structured data -- it's automatically decomposed into entities and
    relations by the underlying extraction pipeline.

    Args:
        content: The fact, decision, or observation to remember, as a
            clear natural-language statement (e.g. "The team decided to
            use FalkorDB's native vector index instead of Postgres
            pgvector because FalkorDB doesn't combine vector search with
            property filters well, so tenant isolation needed to be
            structural").
        extra_scope: Optional additional scope keys (e.g. {"project": "x"},
            {"agent_id": "y"}) to narrow where this memory is filed. The
            tenant is fixed by this server's API key and cannot be set here.

    Returns:
        A short confirmation naming the entities that were extracted.
    """
    memory = await client.remember(
        content=content,
        source="mcp",
        extra_scope=extra_scope,
    )
    return _format_remember_result(memory)


@mcp.tool()
async def contextstore_recall(query: str, extra_scope: dict[str, str] | None = None) -> str:
    """Search long-term memory for facts relevant to a question or topic.

    Use this before answering questions that might be informed by
    previously stored facts, decisions, or observations -- especially
    anything from past conversations that wouldn't otherwise be in the
    current context window. Don't use this for questions answerable from
    general knowledge or from what's already been discussed in this
    conversation.

    Args:
        query: A natural-language question or topic to search for (e.g.
            "What database did we choose for vector search and why?").
        extra_scope: Optional additional scope keys to narrow the search. The
            tenant is fixed by this server's API key and cannot be set here.

    Returns:
        A natural-language answer to the query, synthesised from the matching
        memories and grounded strictly in what was stored (it will say so when
        the stored memories don't contain enough to answer). Falls back to a
        compact list of matching entities and relations if synthesis is
        unavailable, or a message saying nothing was found.
    """
    result = await client.recall(
        query=query,
        extra_scope=extra_scope,
        synthesise=True,
    )
    return _format_recall_result(result)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
