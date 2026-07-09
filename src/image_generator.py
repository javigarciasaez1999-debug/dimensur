from __future__ import annotations

import base64
import hashlib
import io
import logging
import random
from pathlib import Path

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter

from .models import GeneratedContent, ImageData, ImagePlan
from .utils import slugify


class ImageGenerationError(RuntimeError):
    pass


IMAGE_SYSTEM_PROMPT = """
Eres director de arte editorial especializado en contenidos inmobiliarios y
urbanos de Almería. Diseña conceptos fotográficos concretos, realistas y
publicables. Evita clichés, repeticiones, texto incrustado, logos, marcas,
personas reconocibles en primer plano y estética artificial.
""".strip()


class ImageGenerator:
    def __init__(
        self,
        api_key: str,
        text_model: str,
        image_model: str,
        timeout_seconds: float,
        image_size: str,
        image_quality: str,
        images_dir: Path,
        logger: logging.Logger,
    ) -> None:
        if not api_key:
            raise ImageGenerationError("OPENAI_API_KEY está vacío.")
        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.text_model = text_model
        self.image_model = image_model
        self.image_size = image_size
        self.image_quality = image_quality
        self.images_dir = images_dir
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    def plan_image(
        self,
        *,
        content: GeneratedContent,
        previous_concept: str,
        used_concepts: list[str],
        attempt: int,
        rejection_reason: str = "",
    ) -> ImagePlan:
        prompt = f"""
Prepara el concepto de imagen para esta noticia.

Título: {content.title}
Resumen: {content.summary}
Ángulo editorial: {content.editorial_angle}
Propuesta inicial: {content.image_concept}

Concepto visual anterior:
{previous_concept or "No existe"}

Últimos conceptos ya usados:
{used_concepts[-20:]}

Reglas:
- La escena debe representar el tema específico, no “un edificio moderno” genérico.
- Debe variar radicalmente respecto al concepto anterior y al historial.
- Fotografía editorial inmobiliaria realista, luminosa, profesional y mediterránea.
- Sin texto, logos, marcas ni personas reconocibles en primer plano.
- Sin llaves sobre planos, pareja mirando vivienda o fachada genérica salvo que
  el tema lo haga imprescindible y no aparezca en el historial.
- El prompt final debe describir composición, punto de vista, luz, entorno y
  elementos que deben evitarse.
- El ALT debe describir la imagen con naturalidad y sin relleno SEO.

Intento: {attempt}
Motivo de rechazo anterior: {rejection_reason or "Ninguno"}
""".strip()
        try:
            response = self.client.responses.parse(
                model=self.text_model,
                input=[
                    {"role": "system", "content": IMAGE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                text_format=ImagePlan,
                max_output_tokens=1_200,
            )
        except Exception as exc:
            raise ImageGenerationError(
                f"OpenAI no pudo planificar la imagen: {exc}"
            ) from exc
        if response.output_parsed is None:
            raise ImageGenerationError(
                "OpenAI no devolvió un concepto de imagen estructurado."
            )
        return response.output_parsed

    @staticmethod
    def final_prompt(plan: ImagePlan, content: GeneratedContent) -> str:
        return (
            f"Imagen editorial realista para una noticia inmobiliaria sobre "
            f"{content.title}. Representar: {plan.concept}. {plan.prompt}. "
            "Estilo fotográfico profesional, luminoso y mediterráneo, relacionado "
            "con Almería, composición horizontal limpia apta para cabecera web, "
            "detalle natural y materiales creíbles. Sin texto incrustado, sin "
            "logos, sin marcas inventadas, sin marcas de agua, sin personas "
            "reconocibles en primer plano, sin estética futurista exagerada."
        )

    def generate(
        self,
        *,
        plan: ImagePlan,
        content: GeneratedContent,
        simulate: bool = False,
    ) -> ImageData:
        filename = f"{slugify(content.slug or content.title)}.jpg"
        local_path = self.images_dir / filename
        prompt = self.final_prompt(plan, content)

        if simulate:
            image_bytes = self._create_placeholder(plan.concept)
        else:
            try:
                result = self.client.images.generate(
                    model=self.image_model,
                    prompt=prompt,
                    size=self.image_size,
                    quality=self.image_quality,
                    output_format="jpeg",
                    output_compression=85,
                )
                encoded = result.data[0].b64_json if result.data else None
                if not encoded:
                    raise ImageGenerationError(
                        "La API de imágenes no devolvió datos base64."
                    )
                image_bytes = base64.b64decode(encoded, validate=True)
            except ImageGenerationError:
                raise
            except Exception as exc:
                raise ImageGenerationError(
                    f"OpenAI no pudo generar la imagen: {exc}"
                ) from exc

        try:
            local_path.write_bytes(image_bytes)
        except OSError as exc:
            raise ImageGenerationError(
                f"No se pudo guardar la imagen en {local_path}: {exc}"
            ) from exc

        return ImageData(
            filename=filename,
            base64_data=base64.b64encode(image_bytes).decode("ascii"),
            prompt=prompt,
            concept=plan.concept.strip(),
            alt=plan.alt.strip(),
            difference_vs_previous=plan.difference_vs_previous.strip(),
            local_path=local_path,
            simulated=simulate,
        )

    @staticmethod
    def _create_placeholder(concept: str) -> bytes:
        """Crea un marcador visual único para pruebas sin gastar una generación."""
        digest = hashlib.sha256(concept.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big")
        randomizer = random.Random(seed)
        width, height = 1536, 1024
        first = tuple(90 + digest[index] % 120 for index in range(3))
        second = tuple(50 + digest[index + 3] % 150 for index in range(3))
        image = Image.new("RGB", (width, height), first)
        pixels = image.load()
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(
                int(first[channel] * (1 - ratio) + second[channel] * ratio)
                for channel in range(3)
            )
            for x in range(width):
                pixels[x, y] = color

        draw = ImageDraw.Draw(image, "RGBA")
        for _ in range(18):
            x = randomizer.randint(-200, width)
            y = randomizer.randint(-100, height)
            w = randomizer.randint(180, 600)
            h = randomizer.randint(80, 360)
            shade = tuple(randomizer.randint(180, 255) for _ in range(3)) + (35,)
            draw.rounded_rectangle((x, y, x + w, y + h), 24, fill=shade)
        image = image.filter(ImageFilter.GaussianBlur(radius=5))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82, optimize=True)
        return buffer.getvalue()
