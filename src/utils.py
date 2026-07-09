from __future__ import annotations

import json
import re
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from slugify import slugify as python_slugify


def slugify(value: str) -> str:
    return python_slugify(value, lowercase=True, separator="-")


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "si", "sí", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).isoformat(timespec="seconds")


def html_to_text(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def word_count_html(html: str) -> int:
    return len(re.findall(r"\b[\wÁÉÍÓÚÜÑáéíóúüñ]+\b", html_to_text(html)))


def extract_h2(html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    return [heading.get_text(" ", strip=True) for heading in soup.find_all("h2")]


def extract_links(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    return [
        {"url": link.get("href", "").strip(), "anchor": link.get_text(" ", strip=True)}
        for link in soup.find_all("a")
        if link.get("href")
    ]


def looks_like_html(value: str) -> bool:
    soup = BeautifulSoup(value or "", "html.parser")
    return bool(soup.find(["p", "h2", "h3", "ul", "li"]))


def contains_markdown_fence(value: str) -> bool:
    return "```" in (value or "")


def safe_json_dumps(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(value, ensure_ascii=False, indent=indent, default=str)


def compact_for_sheet(value: Any, max_chars: int = 45_000) -> str:
    text = value if isinstance(value, str) else safe_json_dumps(value)
    if len(text) <= max_chars:
        return text
    return (
        text[: max_chars - 120] + "\n...[TRUNCADO; consulte el archivo local indicado]"
    )


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def ensure_directories(project_root: Path) -> None:
    for relative in ("logs", "data", "data/images", "data/payloads"):
        (project_root / relative).mkdir(parents=True, exist_ok=True)


def find_published_url(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    keys = ("url", "published_url", "public_url", "link")
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    for value in payload.values():
        nested = find_published_url(value)
        if nested:
            return nested
    return ""
