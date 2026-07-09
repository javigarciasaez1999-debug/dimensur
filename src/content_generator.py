from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup
from openai import OpenAI

from .models import GeneratedContent, InternalLink
from .utils import (
    contains_markdown_fence,
    extract_h2,
    extract_links,
    safe_json_dumps,
    slugify,
    word_count_html,
)


class ContentGenerationError(RuntimeError):
    pass


class ContentValidationError(ContentGenerationError):
    pass


SYSTEM_PROMPT = """
Actúa como redactor SEO profesional especializado en mercado inmobiliario,
obra nueva y contenido local de Almería. Escribes noticias útiles para Dimensur
en español, con criterio editorial humano, precisión y tono profesional cercano.

Prioridades:
- No inventes cifras, características de promociones, plazos, precios ni hechos.
- Cada pieza debe tener un enfoque, estructura, introducción y cierre propios.
- Usa exclusivamente los enlaces internos proporcionados.
- El HTML final no debe incluir Markdown, html, head, body, scripts ni estilos.
- Evita el lenguaje promocional excesivo, las muletillas y los emojis.
- La respuesta debe cumplir exactamente el esquema estructurado solicitado.
""".strip()


def _previous_context(previous: dict[str, Any] | None) -> dict[str, Any]:
    previous = previous or {}
    html = str(previous.get("html", ""))
    return {
        "title": previous.get("title", ""),
        "summary": previous.get("summary", ""),
        "editorial_angle": previous.get("editorial_angle", ""),
        "h2": previous.get("h2") or extract_h2(html),
        "cta": previous.get("cta", ""),
        "internal_links_used": previous.get("internal_links_used", []),
        "image_concept": previous.get("image_concept", ""),
        "html_excerpt": html[:8_000],
    }


def build_content_prompt(
    *,
    base_title: str,
    main_keyword: str,
    company_context: str,
    allowed_links: list[dict[str, object]],
    previous: dict[str, Any] | None,
    min_words: int,
    max_words: int,
    min_links: int,
    max_links: int,
    attempt: int,
    rejection_reason: str,
) -> str:
    previous_context = _previous_context(previous)
    retry_context = (
        f"\nLa propuesta anterior fue rechazada por: {rejection_reason}\n"
        "Corrige ese problema y cambia de forma sustancial el planteamiento."
        if rejection_reason
        else ""
    )
    return f"""
Redacta una noticia para Dimensur.

REGLAS EDITORIALES ESTABLES
- Artículo entre {min_words} y {max_words} palabras, contadas sobre el texto visible.
- Introducción breve, varios H2 y H3 solo cuando aporten claridad.
- Párrafos claros; listas únicamente cuando mejoren la comprensión.
- Incluye una llamada a la acción final suave y específica.
- No repitas sistemáticamente “En Dimensur”.
- No uses frases de relleno, Markdown, emojis ni etiquetas html/head/body.
- Usa HTML limpio: h2, h3, p, ul, li, strong y a.
- El título SEO debe ser natural y no superar aproximadamente 65 caracteres.
- La metadescripción debe ser atractiva y rondar 140-160 caracteres.
- El extracto debe funcionar como subtítulo periodístico.

REGLAS ANTI-REPETICIÓN
- No repitas el enfoque, estructura, H2, introducción, CTA, argumentos,
  ejemplos, enlaces ni orden de ideas del artículo anterior.
- Si el tema es parecido, elige una perspectiva claramente diferente.
- Explica en difference_vs_previous cuál es la diferencia concreta.
- editorial_angle debe resumir el ángulo elegido.
- cta debe contener el cierre o llamada a la acción usados.

ENLAZADO
- Usa entre {min_links} y {max_links} enlaces cuando sean semánticamente
  relevantes. Si solo encaja uno de forma natural, usa uno.
- Solo puedes utilizar URLs de la lista permitida.
- Integra los enlaces en zonas distintas del artículo, con anchors naturales.
- internal_links_used debe reflejar exactamente los enlaces insertados.

CONTEXTO CORPORATIVO (úsalo como fuente, no lo copies mecánicamente)
{company_context}

ENLACES PERMITIDOS
{safe_json_dumps(allowed_links, indent=2)}

ARTÍCULO ANTERIOR
{safe_json_dumps(previous_context, indent=2)}

DATOS DE ESTA NOTICIA
Título base: {base_title}
Keyword principal: {main_keyword or "No indicada"}
Intento de generación: {attempt}
{retry_context}

Genera una pieza única. El campo image_concept debe proponer una escena visual
específica y distinta al concepto anterior; image_prompt e image_alt deben ser
coherentes con ella. No incluyas texto incrustado dentro de la imagen propuesta.
""".strip()


def _sanitize_html(html: str) -> str:
    if contains_markdown_fence(html):
        raise ContentValidationError("El HTML contiene un bloque Markdown ```.")
    soup = BeautifulSoup(html, "html.parser")
    if soup.find(["script", "style", "iframe"]):
        raise ContentValidationError("El HTML contiene etiquetas no permitidas.")

    allowed_tags = {"h2", "h3", "p", "ul", "li", "strong", "a"}
    for tag in list(soup.find_all(True)):
        if tag.name not in allowed_tags:
            tag.unwrap()
            continue
        attributes = dict(tag.attrs)
        tag.attrs = {}
        if tag.name == "a" and attributes.get("href"):
            tag["href"] = str(attributes["href"]).strip()
    return str(soup).strip()


def validate_generated_content(
    content: GeneratedContent,
    *,
    allowed_links: list[dict[str, object]],
    min_words: int,
    max_words: int,
    max_links: int,
) -> GeneratedContent:
    content.html = _sanitize_html(content.html)
    content.slug = slugify(content.slug or content.title)

    count = word_count_html(content.html)
    if count < min_words or count > max_words:
        raise ContentValidationError(
            f"Longitud inválida: {count} palabras; rango {min_words}-{max_words}."
        )
    if not extract_h2(content.html):
        raise ContentValidationError("El artículo no contiene ningún H2.")
    if len(content.seo_title.strip()) < 30 or len(content.seo_title.strip()) > 75:
        raise ContentValidationError(
            f"Longitud de título SEO poco razonable: {len(content.seo_title.strip())}."
        )
    if (
        len(content.meta_description.strip()) < 110
        or len(content.meta_description.strip()) > 175
    ):
        raise ContentValidationError(
            "La metadescripción debe tener entre 110 y 175 caracteres."
        )

    allowed_urls = {str(item.get("url", "")).strip() for item in allowed_links}
    html_links = extract_links(content.html)
    html_urls = [item["url"] for item in html_links]
    invented = sorted(set(html_urls) - allowed_urls)
    if invented:
        raise ContentValidationError(
            "El modelo insertó enlaces no permitidos: " + ", ".join(invented)
        )
    if len(html_links) > max_links:
        raise ContentValidationError(
            f"Se insertaron {len(html_links)} enlaces; máximo permitido: {max_links}."
        )

    declared = [
        {"url": item.url.strip(), "anchor": item.anchor.strip()}
        for item in content.internal_links_used
    ]
    if declared != html_links:
        content.internal_links_used = [InternalLink(**item) for item in html_links]

    if not content.title.strip() or not content.summary.strip():
        raise ContentValidationError("Faltan título o resumen.")
    return content


class ContentGenerator:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        logger: logging.Logger,
    ) -> None:
        if not api_key:
            raise ContentGenerationError("OPENAI_API_KEY está vacío.")
        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model = model
        self.logger = logger

    def generate(
        self,
        *,
        base_title: str,
        main_keyword: str,
        company_context: str,
        allowed_links: list[dict[str, object]],
        previous: dict[str, Any] | None,
        min_words: int,
        max_words: int,
        min_links: int,
        max_links: int,
        attempt: int = 1,
        rejection_reason: str = "",
    ) -> GeneratedContent:
        prompt = build_content_prompt(
            base_title=base_title,
            main_keyword=main_keyword,
            company_context=company_context,
            allowed_links=allowed_links,
            previous=previous,
            min_words=min_words,
            max_words=max_words,
            min_links=min_links,
            max_links=max_links,
            attempt=attempt,
            rejection_reason=rejection_reason,
        )
        try:
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                text_format=GeneratedContent,
                max_output_tokens=8_000,
            )
        except Exception as exc:
            raise ContentGenerationError(
                f"OpenAI no pudo generar el contenido: {exc}"
            ) from exc

        parsed = response.output_parsed
        if parsed is None:
            self.logger.error("Respuesta OpenAI sin output_parsed: %s", response)
            raise ContentGenerationError(
                "OpenAI no devolvió contenido estructurado utilizable."
            )
        return validate_generated_content(
            parsed,
            allowed_links=allowed_links,
            min_words=min_words,
            max_words=max_words,
            max_links=max_links,
        )
