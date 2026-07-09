from __future__ import annotations

import difflib
import re
from typing import Iterable

from .models import SimilarityResult
from .utils import html_to_text, normalize_space

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:  # pragma: no cover - fallback para instalaciones mínimas
    TfidfVectorizer = None
    cosine_similarity = None


def _normalize(value: str) -> str:
    text = normalize_space(html_to_text(value)).lower()
    return re.sub(r"[^\wáéíóúüñ ]+", " ", text)


def _pair_similarity(first: str, second: str) -> tuple[float, str]:
    first_normalized = _normalize(first)
    second_normalized = _normalize(second)
    if not first_normalized or not second_normalized:
        return 0.0, "No hay suficiente texto comparable."

    if TfidfVectorizer is not None and cosine_similarity is not None:
        try:
            matrix = TfidfVectorizer(
                ngram_range=(1, 2), stop_words=None, min_df=1
            ).fit_transform([first_normalized, second_normalized])
            score = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
            return score, "Similitud léxica TF-IDF/coseno."
        except ValueError:
            pass

    score = difflib.SequenceMatcher(None, first_normalized, second_normalized).ratio()
    return float(score), "Similitud de secuencia (fallback)."


def compare_articles(
    new_html: str,
    previous_html: str,
    *,
    threshold: float = 0.58,
    new_h2: Iterable[str] = (),
    previous_h2: Iterable[str] = (),
) -> SimilarityResult:
    if not previous_html.strip():
        return SimilarityResult(
            score=0.0,
            explanation="No existe un artículo anterior comparable.",
            decision="aceptado",
        )

    content_score, method = _pair_similarity(new_html, previous_html)
    old_headings = {_normalize(item) for item in previous_h2 if item.strip()}
    new_headings = {_normalize(item) for item in new_h2 if item.strip()}
    heading_overlap = len(old_headings & new_headings) / max(
        1, len(old_headings | new_headings)
    )
    combined_score = min(1.0, content_score * 0.85 + heading_overlap * 0.15)
    decision = "regenerar" if combined_score >= threshold else "aceptado"
    explanation = (
        f"{method} contenido={content_score:.3f}; "
        f"solapamiento H2={heading_overlap:.3f}; "
        f"score combinado={combined_score:.3f}; umbral={threshold:.3f}."
    )
    return SimilarityResult(combined_score, explanation, decision)


def compare_concept_to_history(
    concept: str,
    previous_concept: str,
    used_concepts: Iterable[str],
    *,
    threshold: float = 0.52,
) -> SimilarityResult:
    candidates = [previous_concept, *used_concepts]
    candidates = [item for item in candidates if item and item.strip()]
    if not candidates:
        return SimilarityResult(
            score=0.0,
            explanation="No existen conceptos visuales anteriores.",
            decision="aceptado",
        )

    scored = [(_pair_similarity(concept, item)[0], item) for item in candidates]
    max_score, closest = max(scored, key=lambda pair: pair[0])
    decision = "regenerar" if max_score >= threshold else "aceptado"
    explanation = (
        f"Máxima similitud visual textual={max_score:.3f}; "
        f"umbral={threshold:.3f}; concepto más cercano: {closest[:180]}"
    )
    return SimilarityResult(max_score, explanation, decision)
