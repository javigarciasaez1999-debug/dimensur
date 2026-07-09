from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.automation import EditorialAutomation
from src.logger_setup import setup_logging
from src.settings import load_settings
from src.sheets_client import create_sheet_client
from src.utils import ensure_directories


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatización editorial de noticias para Dimensur."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Genera y guarda todo, pero no llama a la API de Dimensur.",
    )
    mode.add_argument(
        "--publish",
        action="store_true",
        help="Publica aunque DRY_RUN=true en el archivo .env.",
    )
    parser.add_argument(
        "--row",
        type=int,
        help="Procesa una fila concreta de la hoja (la cabecera es la fila 1).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    ensure_directories(project_root)

    try:
        settings = load_settings(project_root)
    except Exception as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    logger = setup_logging(project_root / "logs" / "automation.log", settings.log_level)
    dry_run = settings.dry_run
    if args.dry_run:
        dry_run = True
    elif args.publish:
        dry_run = False

    try:
        sheet = create_sheet_client(settings, logger)
        automation = EditorialAutomation(settings, sheet, logger)
        success = automation.run(
            dry_run=dry_run,
            row_number=args.row,
            allow_generated_row=args.publish,
        )
        return 0 if success else 1
    except Exception as exc:
        logger.exception("Error fatal antes de procesar una fila: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
