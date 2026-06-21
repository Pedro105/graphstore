"""Shared limit/offset pagination for list endpoints.

One dependency so every paginated endpoint accepts the same query params with
the same bounds and defaults. Backwards-compatible: callers that omit the params
get the first page at the default size, and the response stays a plain list (no
envelope), so existing clients keep working.

limit/offset (not cursors) on purpose: these are admin/dashboard list views over
modest, ordered tables, where offset paging is simplest and maps directly onto
Postgres LIMIT/OFFSET. Cursor paging's stability/scale benefits don't pay for
their added complexity here.
"""

from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Pagination(BaseModel):
    limit: int
    offset: int


def pagination_params(
    limit: int = Query(
        default=DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Maximum rows to return (1-{MAX_LIMIT}, default {DEFAULT_LIMIT}).",
    ),
    offset: int = Query(default=0, ge=0, description="Number of rows to skip (default 0)."),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PaginationDep = Annotated[Pagination, Depends(pagination_params)]
