from datetime import datetime

from pydantic import BaseModel, Field


class Section(BaseModel):
    heading: str = Field(default="", max_length=150)
    body: str = Field(default="", max_length=5_000)


class PageDraftUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    summary: str = Field(default="", max_length=500)
    sections: list[Section] = Field(default_factory=list, max_length=30)
    seo_description: str = Field(default="", max_length=300)


class PageVersion(BaseModel):
    title: str
    summary: str
    sections: list[Section]
    seo_description: str


class PageAdminOut(BaseModel):
    slug: str
    label: str
    draft: PageVersion
    published: PageVersion | None
    published_at: datetime | None
    has_unpublished_changes: bool
    updated_at: datetime | None
    can_edit: bool = False
    can_publish: bool = False


class PageListItem(BaseModel):
    slug: str
    label: str
    is_published: bool
    has_unpublished_changes: bool
    published_at: datetime | None
    updated_at: datetime | None


class PublicPage(BaseModel):
    slug: str
    title: str
    summary: str
    sections: list[Section]
    seo_description: str
    published_at: datetime
