from __future__ import annotations

from typing import Any

from .models import GeneratedContent, ImageData
from .utils import contains_markdown_fence, looks_like_html


class PayloadValidationError(ValueError):
    pass


def build_payload(
    generated_content: GeneratedContent,
    image_data: ImageData,
    *,
    author: str,
    categories: str,
    published_at: str = "",
) -> dict[str, Any]:
    payload = {
        "title": generated_content.title.strip(),
        "subtitle": generated_content.excerpt.strip()
        or generated_content.meta_description.strip(),
        "news": generated_content.html.strip(),
        "author": author.strip(),
        "categories": (categories or generated_content.category).strip(),
        "published_at": published_at,
        "image": {
            "filename": image_data.filename.strip(),
            "data": image_data.base64_data.strip(),
        },
        "seo": {
            "title": generated_content.seo_title.strip(),
            "description": generated_content.meta_description.strip(),
        },
    }
    validate_payload(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> None:
    required = {
        "title": payload.get("title"),
        "news": payload.get("news"),
        "seo.title": (payload.get("seo") or {}).get("title"),
        "seo.description": (payload.get("seo") or {}).get("description"),
        "image.filename": (payload.get("image") or {}).get("filename"),
        "image.data": (payload.get("image") or {}).get("data"),
    }
    empty = [name for name, value in required.items() if not str(value or "").strip()]
    if empty:
        raise PayloadValidationError(
            "Faltan campos obligatorios del payload: " + ", ".join(empty)
        )
    news = str(payload["news"])
    if not looks_like_html(news):
        raise PayloadValidationError("El contenido no parece HTML válido.")
    if contains_markdown_fence(news):
        raise PayloadValidationError("El contenido incluye bloques Markdown ```.")


def payload_for_sheet(
    payload: dict[str, Any], *, payload_file: str, simulated_image: bool
) -> dict[str, Any]:
    safe_payload = {
        **payload,
        "image": {
            **payload["image"],
            "data": (
                f"<BASE64 OMITIDO EN HOJA; {len(payload['image']['data'])} caracteres>"
            ),
        },
        "_local_payload_file": payload_file,
        "_simulated_image": simulated_image,
    }
    return safe_payload
