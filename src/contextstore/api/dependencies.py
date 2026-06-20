"""FastAPI dependency injection for shared backend clients.

Both GraphStore and EmbeddingProvider instances are constructed once in
api/app.py's lifespan and stored on app.state; these dependencies just
hand callers that shared instance rather than constructing a new one per
request.
"""

from typing import Annotated

from fastapi import Depends, Request

from contextstore.graph.store import GraphStore
from contextstore.vector.embeddings import EmbeddingProvider


def get_graph_store(request: Request) -> GraphStore:
    graph_store: GraphStore = request.app.state.graph_store
    return graph_store


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    embedding_provider: EmbeddingProvider = request.app.state.embedding_provider
    return embedding_provider


GraphStoreDep = Annotated[GraphStore, Depends(get_graph_store)]
EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
