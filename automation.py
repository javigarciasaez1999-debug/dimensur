from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .config_loader import load_editorial_config, parse_allowed_links
from .content_generator import ContentGenerator
from .dimensur_api import DimensurApiClient
from .history_manager import HistoryManager
from .image_generator import ImageGenerator
from .json_builder import build_payload, payload_for_sheet
from .models import GeneratedContent, ImageData, ImagePlan, SheetRow
from .settings import Settings
from .sheets_client import BaseSheetsClient
from .similarity_checker import compare_articles, compare_concept_to_history
from .utils import (
    compact_for_sheet,
    extract_h2,
    now_iso,
    safe_json_dumps,
)


class AutomationError(RuntimeError):
    pass


class EditorialAutomation:
    def __init__(
        self,
        settings: Settings,
        sheet: BaseSheetsClient,
        logger: logging.Logger,
    ) -> None:
        self.settings = settings
        self.sheet = sheet
        self.logger = logger
        self.history = HistoryManager(
            settings.project_root / "data" / "historial_publicaciones.json",
            settings.project_root / "data" / "imagenes_usadas.json",
        )

    def run(
        self,
        *,
        dry_run: bool,
        row_number: int | None = None,
        allow_generated_row: bool = False,
    ) -> bool:
        self.logger.info("Inicio de ejecución | dry_run=%s", dry_run)
        self.sheet.load_sheet()
        self.sheet.require_headers()

        row = self._select_row(row_number, allow_generated_row)
        if row is None:
            self.logger.info("No hay noticias pendientes")
            return True

        title = row.get("Título base")
        source_id = row.get("ID") or f"row-{row.row_number}"
        self.logger.info(
            "Fila seleccionada=%s | id=%s | título=%s",
            row.row_number,
            source_id,
            title,
        )

        try:
            self._claim_row(
                row,
                allow_generated_row,
                explicit_row=row_number is not None,
            )
            if not title:
                raise AutomationError("La columna Título base está vacía.")

            editorial_config = load_editorial_config(self.settings.project_root)
            allowed_links = parse_allowed_links(editorial_config.internal_links_text)
            if not allowed_links:
                raise AutomationError(
                    "No se pudo extraer ningún enlace de enlazado_interno.txt."
                )
            self.logger.info(
                "Archivos de configuración cargados | enlaces=%s", len(allowed_links)
            )

            previous = self._load_previous(row.row_number, source_id)
            generated = self._generate_content(
                row=row,
                company_context=editorial_config.company_context,
                allowed_links=allowed_links,
                previous=previous,
            )
            image_plan = self._plan_image(generated, previous)
            image = self._generate_image(
                generated,
                image_plan,
                simulate=dry_run and not self.settings.generate_images_in_dry_run,
            )

            categories = (
                row.get("Categoría")
                or generated.category
                or self.settings.default_categories
            )
            payload = build_payload(
                generated,
                image,
                author=self.settings.default_author,
                categories=categories,
            )
            payload_path = self.history.save_payload(generated.slug, payload)
            self.logger.info("JSON creado y archivado en %s", payload_path)

            generated_fields = self._generated_sheet_fields(
                generated=generated,
                image=image,
                payload=payload,
                payload_path=payload_path,
                categories=categories,
            )
            self.sheet.update_row_fields(row.row_number, generated_fields)
            self.logger.info("Campos generados guardados en la hoja")

            timestamp = now_iso(self.settings.timezone)
            if dry_run:
                api_response: dict[str, Any] | str = "DRY_RUN: no enviado"
                published_url = ""
                final_status = "Generado - No publicado"
            else:
                if image.simulated:
                    raise AutomationError(
                        "No se permite publicar una imagen simulada de dry-run."
                    )
                self.logger.info("Enviando noticia a la API de Dimensur")
                api_result = DimensurApiClient(
                    self.settings.dimensur_api_url,
                    self.settings.dimensur_api_token,
                    self.settings.dimensur_api_timeout_seconds,
                ).publish_news(payload)
                api_response = {
                    "success": api_result.success,
                    "status_code": api_result.status_code,
                    "response_text": api_result.response_text,
                    "response_json": api_result.response_json,
                }
                published_url = api_result.published_url
                if not api_result.success:
                    error_message = (
                        f"Error de API Dimensur (HTTP {api_result.status_code}): "
                        f"{api_result.response_text}"
                    )
                    self.sheet.update_row_fields(
                        row.row_number,
                        {
                            "Estado": "Error",
                            "Respuesta API": compact_for_sheet(api_response),
                            "Error": compact_for_sheet(error_message),
                        },
                    )
                    raise AutomationError(error_message)
                final_status = "Subida"

            self._save_history(
                source_id=source_id,
                generated=generated,
                image=image,
                timestamp=timestamp,
                api_response=api_response,
                published_url=published_url,
                status=final_status,
            )

            final_fields = {
                "Estado": final_status,
                "Respuesta API": compact_for_sheet(api_response),
                "URL publicada": published_url,
                "Fecha publicación": timestamp,
                "Error": "",
            }
            try:
                self.sheet.update_row_fields(row.row_number, final_fields)
            except Exception:
                if not dry_run:
                    self.logger.critical(
                        "La API publicó la noticia pero no se pudo actualizar la hoja. "
                        "Payload local=%s | URL=%s",
                        payload_path,
                        published_url,
                        exc_info=True,
                    )
                raise

            self.logger.info(
                "Final correcto | fila=%s | estado=%s",
                row.row_number,
                final_status,
            )
            return True
        except Exception as exc:
            self.logger.exception("La automatización terminó con error: %s", exc)
            self._mark_error(row.row_number, str(exc))
            return False

    def _select_row(
        self, row_number: int | None, allow_generated_row: bool
    ) -> SheetRow | None:
        if row_number is not None:
            return self.sheet.get_row(row_number)
        statuses = (
            ("Crear", "Generado - No publicado") if allow_generated_row else ("Crear",)
        )
        return self.sheet.find_next_pending_row(statuses=statuses)

    def _claim_row(
        self,
        row: SheetRow,
        allow_generated_row: bool,
        *,
        explicit_row: bool,
    ) -> None:
        current = self.sheet.get_row(row.row_number)
        accepted = {"Crear"}
        if allow_generated_row:
            accepted.add("Generado - No publicado")
        if explicit_row:
            accepted.update({"Generado - No publicado", "Error"})
        if current.get("Estado") not in accepted:
            raise AutomationError(
                f"La fila {row.row_number} ya no está disponible; "
                f"Estado actual={current.get('Estado')!r}."
            )
        self.sheet.update_row_fields(
            row.row_number, {"Estado": "Generando", "Error": ""}
        )
        self.logger.info("Estado cambiado a Generando")

    def _load_previous(self, current_row: int, source_id: str) -> dict[str, Any] | None:
        sheet_previous = self.sheet.get_last_published_article(exclude_row=current_row)
        local_previous = self.history.latest_publication(exclude_source_id=source_id)
        if local_previous and sheet_previous:
            merged = dict(sheet_previous)
            merged.update(local_previous)
            if not merged.get("html"):
                merged["html"] = sheet_previous.get("html", "")
            return merged
        return local_previous or sheet_previous

    def _generate_content(
        self,
        *,
        row: SheetRow,
        company_context: str,
        allowed_links: list[dict[str, object]],
        previous: dict[str, Any] | None,
    ) -> GeneratedContent:
        generator = ContentGenerator(
            self.settings.openai_api_key,
            self.settings.openai_text_model,
            self.settings.openai_timeout_seconds,
            self.logger,
        )
        rejection_reason = ""
        previous_html = str(
            (previous or {}).get("html") or (previous or {}).get("html_excerpt") or ""
        )
        previous_h2 = (previous or {}).get("h2") or extract_h2(previous_html)

        for attempt in range(1, self.settings.max_regeneration_attempts + 1):
            self.logger.info("Generando contenido | intento=%s", attempt)
            try:
                content = generator.generate(
                    base_title=row.get("Título base"),
                    main_keyword=row.get("Keyword principal"),
                    company_context=company_context,
                    allowed_links=allowed_links,
                    previous=previous,
                    min_words=self.settings.min_content_words,
                    max_words=self.settings.max_content_words,
                    min_links=self.settings.min_internal_links,
                    max_links=self.settings.max_internal_links,
                    attempt=attempt,
                    rejection_reason=rejection_reason,
                )
            except Exception as exc:
                rejection_reason = str(exc)
                self.logger.warning(
                    "Generación de contenido rechazada | intento=%s | %s",
                    attempt,
                    exc,
                )
                continue

            similarity = compare_articles(
                content.html,
                previous_html,
                threshold=self.settings.content_similarity_threshold,
                new_h2=extract_h2(content.html),
                previous_h2=previous_h2,
            )
            self.logger.info(
                "Score de similitud=%.3f | decisión=%s | %s",
                similarity.score,
                similarity.decision,
                similarity.explanation,
            )
            if similarity.decision == "aceptado":
                return content
            rejection_reason = similarity.explanation

        raise AutomationError(
            "El contenido no superó la validación o similitud tras "
            f"{self.settings.max_regeneration_attempts} intentos. "
            f"Último motivo: {rejection_reason}"
        )

    def _plan_image(
        self, generated: GeneratedContent, previous: dict[str, Any] | None
    ) -> ImagePlan:
        generator = self._image_generator()
        previous_concept = str((previous or {}).get("image_concept", ""))
        used_concepts = self.history.image_concepts()
        rejection_reason = ""

        for attempt in range(1, self.settings.max_regeneration_attempts + 1):
            self.logger.info("Planificando imagen | intento=%s", attempt)
            plan = generator.plan_image(
                content=generated,
                previous_concept=previous_concept,
                used_concepts=used_concepts,
                attempt=attempt,
                rejection_reason=rejection_reason,
            )
            similarity = compare_concept_to_history(
                plan.concept,
                previous_concept,
                used_concepts,
                threshold=self.settings.image_similarity_threshold,
            )
            self.logger.info(
                "Similitud visual=%.3f | decisión=%s | %s",
                similarity.score,
                similarity.decision,
                similarity.explanation,
            )
            if similarity.decision == "aceptado":
                return plan
            rejection_reason = similarity.explanation

        raise AutomationError(
            "El concepto visual no fue suficientemente distinto tras "
            f"{self.settings.max_regeneration_attempts} intentos."
        )

    def _image_generator(self) -> ImageGenerator:
        return ImageGenerator(
            api_key=self.settings.openai_api_key,
            text_model=self.settings.openai_text_model,
            image_model=self.settings.openai_image_model,
            timeout_seconds=self.settings.openai_timeout_seconds,
            image_size=self.settings.image_size,
            image_quality=self.settings.image_quality,
            images_dir=self.settings.project_root / "data" / "images",
            logger=self.logger,
        )

    def _generate_image(
        self, generated: GeneratedContent, plan: ImagePlan, *, simulate: bool
    ) -> ImageData:
        self.logger.info(
            "Generando imagen | modo=%s", "simulado" if simulate else "OpenAI"
        )
        return self._image_generator().generate(
            plan=plan, content=generated, simulate=simulate
        )

    def _generated_sheet_fields(
        self,
        *,
        generated: GeneratedContent,
        image: ImageData,
        payload: dict[str, Any],
        payload_path: Path,
        categories: str,
    ) -> dict[str, str]:
        links = [item.url for item in generated.internal_links_used]
        anchors = [item.anchor for item in generated.internal_links_used]
        sheet_payload = payload_for_sheet(
            payload,
            payload_file=str(payload_path),
            simulated_image=image.simulated,
        )
        return {
            "Contenido HTML": compact_for_sheet(generated.html),
            "Título SEO": generated.seo_title,
            "Metadescripción": generated.meta_description,
            "Slug": generated.slug,
            "Categoría": categories,
            "Etiquetas": ", ".join(generated.tags),
            "Enlaces internos usados": safe_json_dumps(links),
            "Anchors usados": safe_json_dumps(anchors),
            "Resumen del contenido generado": generated.summary,
            "Diferencia frente al artículo anterior": generated.difference_vs_previous,
            "Prompt imagen": compact_for_sheet(image.prompt),
            "Concepto visual imagen": image.concept,
            "Diferencia visual frente a imagen anterior": image.difference_vs_previous,
            "URL imagen o nombre archivo": str(image.local_path),
            "ALT imagen": image.alt,
            "JSON enviado": compact_for_sheet(sheet_payload),
            "Error": "",
        }

    def _save_history(
        self,
        *,
        source_id: str,
        generated: GeneratedContent,
        image: ImageData,
        timestamp: str,
        api_response: dict[str, Any] | str,
        published_url: str,
        status: str,
    ) -> None:
        publication = {
            "id": source_id,
            "source_id": source_id,
            "title": generated.title,
            "slug": generated.slug,
            "date": timestamp,
            "status": status,
            "summary": generated.summary,
            "html_excerpt": generated.html[:4_000],
            "h2": extract_h2(generated.html),
            "editorial_angle": generated.editorial_angle,
            "internal_links_used": [
                item.model_dump() for item in generated.internal_links_used
            ],
            "cta": generated.cta,
            "image_concept": image.concept,
            "image_prompt": image.prompt,
            "image_filename": image.filename,
            "image_simulated": image.simulated,
            "api_response": api_response,
            "published_url": published_url,
        }
        image_history = {
            "date": timestamp,
            "title": generated.title,
            "image_concept": image.concept,
            "image_prompt": image.prompt,
            "filename": image.filename,
            "alt": image.alt,
            "simulated": image.simulated,
        }
        self.history.add_publication(publication)
        self.history.add_image(image_history)

    def _mark_error(self, row_number: int, error: str) -> None:
        try:
            self.sheet.update_row_fields(
                row_number,
                {"Estado": "Error", "Error": compact_for_sheet(error)},
            )
        except Exception:
            self.logger.critical(
                "No se pudo marcar la fila %s como Error. Error original: %s",
                row_number,
                error,
                exc_info=True,
            )
