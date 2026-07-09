from src.similarity_checker import compare_articles, compare_concept_to_history


def test_identical_articles_are_rejected() -> None:
    html = "<h2>Mercado local</h2><p>La vivienda nueva crece en Almería.</p>"
    result = compare_articles(
        html,
        html,
        threshold=0.5,
        new_h2=["Mercado local"],
        previous_h2=["Mercado local"],
    )
    assert result.decision == "regenerar"
    assert result.score >= 0.5


def test_unrelated_visual_concept_is_accepted() -> None:
    result = compare_concept_to_history(
        "Detalle cenital de patios interiores y vegetación mediterránea",
        "Llaves sobre un plano de vivienda",
        ["Fachada residencial moderna bajo cielo azul"],
        threshold=0.8,
    )
    assert result.decision == "aceptado"
