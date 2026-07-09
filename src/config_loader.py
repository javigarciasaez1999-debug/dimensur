from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ConfigurationFileError(RuntimeError):
    """Error de configuración editorial legible para el operador."""


@dataclass(frozen=True, slots=True)
class EditorialConfig:
    company_context: str
    internal_links_text: str


def _read_required_file(path: Path) -> str:
    if not path.exists():
        raise ConfigurationFileError(f"No existe el archivo obligatorio: {path}")
    if not path.is_file():
        raise ConfigurationFileError(f"La ruta no es un archivo: {path}")

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ConfigurationFileError(f"El archivo obligatorio está vacío: {path}")
    return content


def load_editorial_config(project_root: Path) -> EditorialConfig:
    config_dir = project_root / "config"
    return EditorialConfig(
        company_context=_read_required_file(config_dir / "info_previa_dimensur.txt"),
        internal_links_text=_read_required_file(config_dir / "enlazado_interno.txt"),
    )


def parse_allowed_links(raw_text: str) -> list[dict[str, object]]:
    links: list[dict[str, object]] = []
    current: dict[str, object] = {}

    def commit() -> None:
        nonlocal current
        if current.get("url"):
            current.setdefault("name", "")
            current.setdefault("topics", [])
            current.setdefault("anchors", [])
            links.append(current)
        current = {}

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "---":
            commit()
            continue
        if line.startswith("URL:"):
            if current.get("url"):
                commit()
            current["url"] = line.partition(":")[2].strip()
        elif line.startswith("Nombre:"):
            current["name"] = line.partition(":")[2].strip()
        elif line.startswith("Temas:"):
            current["topics"] = [
                item.strip()
                for item in line.partition(":")[2].split(",")
                if item.strip()
            ]
        elif line.startswith("Anchors sugeridos:"):
            current["anchors"] = [
                item.strip()
                for item in line.partition(":")[2].split(",")
                if item.strip()
            ]
    commit()
    return links
