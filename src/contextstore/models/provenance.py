"""Provenance: who wrote a piece of knowledge, when, with what confidence and evidence."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    source: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    evidence: list[str] | None = None
    supersedes: list[str] | None = None
