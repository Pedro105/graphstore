"""Import API routes: batch chat import endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from contextstore.api.auth import AuthContext, DbDep, require_api_key
from contextstore.api.dependencies import EmbeddingProviderDep, GraphStoreDep
from contextstore.db import postgres
from contextstore.imports.service import import_chats, ImportResult
from contextstore.models.scope import Scope

router = APIRouter(prefix="/v1/imports")


class ImportedMessageResponse(BaseModel):
    message_index: int
    role: str
    entities_extracted: int
    relations_extracted: int


class ImportedConversationResponse(BaseModel):
    title: str
    messages_imported: int
    messages_skipped: int
    total_entities: int
    total_relations: int


class ChatImportResponse(BaseModel):
    """Response from a chat import operation."""

    import_id: UUID
    source_format: str
    conversations_imported: int
    total_messages: int
    total_entities: int
    total_relations: int
    conversations: list[ImportedConversationResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ChatImportRequest(BaseModel):
    """Request body for JSON-based chat import."""

    content: str = Field(
        min_length=1,
        description="Raw chat export content (ChatGPT JSON, Claude JSON, or markdown transcript).",
    )
    source_prefix: str = Field(
        default="chat-import",
        description="Prefix for the source field in imported memories.",
    )


def _result_to_response(result: ImportResult) -> ChatImportResponse:
    """Convert internal ImportResult to API response."""
    return ChatImportResponse(
        import_id=result.import_id,
        source_format=result.source_format,
        conversations_imported=result.conversations_imported,
        total_messages=result.total_messages,
        total_entities=result.total_entities,
        total_relations=result.total_relations,
        conversations=[
            ImportedConversationResponse(
                title=conv.title,
                messages_imported=conv.messages_imported,
                messages_skipped=conv.messages_skipped,
                total_entities=conv.total_entities,
                total_relations=conv.total_relations,
            )
            for conv in result.conversations
        ],
        errors=result.errors,
    )


@router.post("/chats", response_model=ChatImportResponse)
async def import_chats_json(
    body: ChatImportRequest,
    graph_store: GraphStoreDep,
    embedding_provider: EmbeddingProviderDep,
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> ChatImportResponse:
    """Import chat exports from JSON body.

    Accepts ChatGPT export JSON (conversations.json), Claude export JSON,
    or plain markdown/text transcripts. Auto-detects the format.

    Each message in the conversations is processed through the extraction
    pipeline, extracting entities and relations into the memory graph.
    """
    scope = Scope.from_dict({"tenant_id": auth.tenant_id})

    result = await import_chats(
        content=body.content,
        scope=scope,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        source_prefix=body.source_prefix,
    )

    if result.conversations_imported == 0 and not result.errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No importable conversations found in the provided content.",
        )

    await postgres.log_usage(
        db,
        auth.api_key_id,
        scope.tenant_id,
        "/v1/imports/chats",
        tokens_used=result.total_tokens,
    )

    return _result_to_response(result)


@router.post("/chats/upload", response_model=ChatImportResponse)
async def import_chats_upload(
    file: Annotated[UploadFile, File(description="Chat export file to import")],
    source_prefix: Annotated[str, Form()] = "chat-import",
    graph_store: GraphStoreDep = None,
    embedding_provider: EmbeddingProviderDep = None,
    db: DbDep = None,
    auth: Annotated[AuthContext, Depends(require_api_key)] = None,
) -> ChatImportResponse:
    """Import chat exports from file upload.

    Accepts ChatGPT export JSON (conversations.json), Claude export JSON,
    or plain markdown/text transcripts. Auto-detects the format from content.

    Supported file extensions: .json, .txt, .md
    """
    if file.filename:
        ext = file.filename.lower().split(".")[-1]
        if ext not in ("json", "txt", "md", "markdown"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: .{ext}. Use .json, .txt, or .md files.",
            )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded.",
        )

    scope = Scope.from_dict({"tenant_id": auth.tenant_id})

    result = await import_chats(
        content=content,
        scope=scope,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        source_prefix=source_prefix,
    )

    if result.conversations_imported == 0 and not result.errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No importable conversations found in the uploaded file.",
        )

    await postgres.log_usage(
        db,
        auth.api_key_id,
        scope.tenant_id,
        "/v1/imports/chats",
        tokens_used=result.total_tokens,
    )

    return _result_to_response(result)
