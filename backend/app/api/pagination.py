from fastapi import Query
from pydantic import BaseModel

MAX_PAGE_SIZE = 100


class PageParams(BaseModel):
    limit: int
    offset: int


def page_params(
    limit: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
