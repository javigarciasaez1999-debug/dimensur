from src.utils import extract_h2, slugify, word_count_html


def test_slugify_removes_accents_and_punctuation() -> None:
    title = "Vega de Acá: por qué es una zona con futuro de Almería"
    assert slugify(title) == "vega-de-aca-por-que-es-una-zona-con-futuro-de-almeria"


def test_html_helpers() -> None:
    html = "<h2>Un título</h2><p>Uno dos tres.</p>"
    assert extract_h2(html) == ["Un título"]
    assert word_count_html(html) == 5
