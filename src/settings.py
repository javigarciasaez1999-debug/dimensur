from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .utils import parse_bool


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    openai_api_key: str
    openai_text_model: str
    openai_image_model: str
    sheet_backend: str
    google_sheet_id: str
    google_sheet_name: str
    google_credentials_file: Path
    excel_file_path: Path
    dimensur_api_url: str
    dimensur_api_token: str
    default_author: str
    default_categories: str
    default_status: str
    dry_run: bool
    generate_images_in_dry_run: bool
    max_regeneration_attempts: int
    min_content_words: int
    max_content_words: int
    max_internal_links: int
    min_internal_links: int
    content_similarity_threshold: float
    image_similarity_threshold: float
    openai_timeout_seconds: float
    dimensur_api_timeout_seconds: float
    image_size: str
    image_quality: str
    timezone: str
    log_level: str


def _path_from_env(project_root: Path, name: str, default: str) -> Path:
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else project_root / value


def _extract_google_sheet_id(value: str) -> str:
    value = value.strip()
    marker = "/spreadsheets/d/"
    if marker not in value:
        return value
    return value.split(marker, 1)[1].split("/", 1)[0].split("?", 1)[0].strip()


def _google_sheet_id_from_env() -> str:
    explicit_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if explicit_id:
        return _extract_google_sheet_id(explicit_id)
    return _extract_google_sheet_id(os.getenv("GOOGLE_SHEET_URL", ""))


def load_settings(project_root: Path) -> Settings:
    load_dotenv(project_root / ".env")

    settings = Settings(
        project_root=project_root,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_text_model=os.getenv("OPENAI_TEXT_MODEL", "gpt-5.5").strip(),
        openai_image_model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2").strip(),
        sheet_backend=os.getenv("SHEET_BACKEND", "google").strip().lower(),
        google_sheet_id=_google_sheet_id_from_env(),
        google_sheet_name=os.getenv("GOOGLE_SHEET_NAME", "Noticias").strip(),
        google_credentials_file=_path_from_env(
            project_root, "GOOGLE_CREDENTIALS_FILE", "credentials.json"
        ),
        excel_file_path=_path_from_env(
            project_root, "EXCEL_FILE_PATH", "data/noticias.xlsx"
        ),
        dimensur_api_url=os.getenv(
            "DIMENSUR_API_URL", "https://www.dimensur.es/api/news"
        ).strip(),
        dimensur_api_token=os.getenv("DIMENSUR_API_TOKEN", "").strip(),
        default_author=os.getenv("DEFAULT_AUTHOR", "Dimensur").strip(),
        default_categories=os.getenv("DEFAULT_CATEGORIES", "Noticias").strip(),
        default_status=os.getenv("DEFAULT_STATUS", "publish").strip(),
        dry_run=parse_bool(os.getenv("DRY_RUN"), True),
        generate_images_in_dry_run=parse_bool(
            os.getenv("GENERATE_IMAGES_IN_DRY_RUN"), False
        ),
        max_regeneration_attempts=max(
            1, int(os.getenv("MAX_REGENERATION_ATTEMPTS", "3"))
        ),
        min_content_words=max(1, int(os.getenv("MIN_CONTENT_WORDS", "900"))),
        max_content_words=max(1, int(os.getenv("MAX_CONTENT_WORDS", "1400"))),
        max_internal_links=max(0, int(os.getenv("MAX_INTERNAL_LINKS", "4"))),
        min_internal_links=max(0, int(os.getenv("MIN_INTERNAL_LINKS", "2"))),
        content_similarity_threshold=float(
            os.getenv("CONTENT_SIMILARITY_THRESHOLD", "0.58")
        ),
        image_similarity_threshold=float(
            os.getenv("IMAGE_SIMILARITY_THRESHOLD", "0.52")
        ),
        openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "180")),
        dimensur_api_timeout_seconds=float(
            os.getenv("DIMENSUR_API_TIMEOUT_SECONDS", "60")
        ),
        image_size=os.getenv("IMAGE_SIZE", "1536x1024").strip(),
        image_quality=os.getenv("IMAGE_QUALITY", "medium").strip(),
        timezone=os.getenv("TIMEZONE", "Europe/Madrid").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip(),
    )

    if settings.min_content_words > settings.max_content_words:
        raise ValueError("MIN_CONTENT_WORDS no puede ser mayor que MAX_CONTENT_WORDS.")
    if settings.min_internal_links > settings.max_internal_links:
        raise ValueError(
            "MIN_INTERNAL_LINKS no puede ser mayor que MAX_INTERNAL_LINKS."
        )
    if settings.sheet_backend not in {"google", "excel"}:
        raise ValueError("SHEET_BACKEND debe ser 'google' o 'excel'.")
    return settings
