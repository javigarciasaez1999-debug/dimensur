from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class InternalLink(BaseModel):
    url: str
    anchor: str


class GeneratedContent(BaseModel):
    title: str
    seo_title: str
    meta_description: str
    slug: str
    excerpt: str
    html: str
    category: str
    tags: list[str] = Field(default_factory=list)
    internal_links_used: list[InternalLink] = Field(default_factory=list)
    summary: str
    difference_vs_previous: str
    editorial_angle: str
    cta: str
    image_concept: str
    image_prompt: str
    image_alt: str


class ImagePlan(BaseModel):
    concept: str
    prompt: str
    alt: str
    difference_vs_previous: str


@dataclass(slots=True)
class ImageData:
    filename: str
    base64_data: str
    prompt: str
    concept: str
    alt: str
    difference_vs_previous: str
    local_path: Path
    simulated: bool = False


@dataclass(slots=True)
class SimilarityResult:
    score: float
    explanation: str
    decision: str


@dataclass(slots=True)
class ApiResult:
    success: bool
    status_code: int | None
    response_text: str
    response_json: dict[str, Any] | list[Any] | None = None
    published_url: str = ""


@dataclass(slots=True)
class SheetRow:
    row_number: int
    values: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str = "") -> str:
        value = self.values.get(key, default)
        return str(value).strip() if value is not None else default
