from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class HistoryManager:
    def __init__(self, publications_path: Path, images_path: Path) -> None:
        self.publications_path = publications_path
        self.images_path = images_path
        self._ensure_json_array(self.publications_path)
        self._ensure_json_array(self.images_path)

    @staticmethod
    def _ensure_json_array(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("[]\n", encoding="utf-8")

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"No se puede leer el historial {path}: {exc}") from exc
        if not isinstance(value, list):
            raise RuntimeError(f"El historial debe contener una lista JSON: {path}")
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def _atomic_write(path: Path, items: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(items, handle, ensure_ascii=False, indent=2, default=str)
                handle.write("\n")
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def publications(self) -> list[dict[str, Any]]:
        return self._read(self.publications_path)

    def images(self) -> list[dict[str, Any]]:
        return self._read(self.images_path)

    def latest_publication(
        self, *, exclude_source_id: str = ""
    ) -> dict[str, Any] | None:
        items = self.publications()
        if exclude_source_id:
            items = [
                item
                for item in items
                if str(item.get("source_id", "")) != exclude_source_id
            ]
        return items[-1] if items else None

    def add_publication(self, item: dict[str, Any]) -> None:
        items = self.publications()
        items.append(item)
        self._atomic_write(self.publications_path, items)

    def add_image(self, item: dict[str, Any]) -> None:
        items = self.images()
        items.append(item)
        self._atomic_write(self.images_path, items)

    def image_concepts(self, *, limit: int = 30) -> list[str]:
        concepts = [
            str(item.get("image_concept", "")).strip()
            for item in self.images()
            if item.get("image_concept")
        ]
        return concepts[-limit:]

    def save_payload(self, slug: str, payload: dict[str, Any]) -> Path:
        target = self.publications_path.parent / "payloads" / f"{slug}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_object(target, payload)
        return target

    @staticmethod
    def _atomic_write_object(path: Path, value: dict[str, Any]) -> None:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
                handle.write("\n")
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
