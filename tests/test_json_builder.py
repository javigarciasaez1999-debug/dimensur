from pathlib import Path

import pytest

from src.json_builder import PayloadValidationError, build_payload
from src.models import GeneratedContent, ImageData


def generated_content() -> GeneratedContent:
    return GeneratedContent(
        title="Noticia de prueba",
        seo_title="Noticia inmobiliaria de prueba en Almería",
        meta_description=(
            "Una explicación clara sobre vivienda y entorno urbano en Almería "
            "para compradores que desean tomar decisiones con más contexto."
        ),
        slug="noticia-de-prueba",
        excerpt="Subtítulo informativo",
        html="<p>Introducción.</p><h2>Contexto</h2><p>Contenido útil.</p>",
        category="Noticias",
        tags=["Almería"],
        internal_links_used=[],
        summary="Resumen",
        difference_vs_previous="Otro enfoque",
        editorial_angle="Perspectiva urbana",
        cta="Consulta información",
        image_concept="Detalle urbano",
        image_prompt="Una calle",
        image_alt="Calle de Almería",
    )


def image_data(base64_data: str = "YWJj") -> ImageData:
    return ImageData(
        filename="noticia-de-prueba.jpg",
        base64_data=base64_data,
        prompt="Prompt",
        concept="Concepto",
        alt="Alt",
        difference_vs_previous="Diferente",
        local_path=Path("image.jpg"),
    )


def test_build_payload() -> None:
    payload = build_payload(
        generated_content(),
        image_data(),
        author="Dimensur",
        categories="Noticias",
    )
    assert payload["image"]["data"] == "YWJj"
    assert payload["seo"]["title"].startswith("Noticia")


def test_build_payload_rejects_empty_image() -> None:
    with pytest.raises(PayloadValidationError):
        build_payload(
            generated_content(),
            image_data(""),
            author="Dimensur",
            categories="Noticias",
        )
