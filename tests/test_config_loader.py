from src.config_loader import parse_allowed_links


def test_parse_allowed_links() -> None:
    raw = """
URL: https://example.com/a
Nombre: Ejemplo
Temas: vivienda, Almería
Anchors sugeridos: ejemplo, vivienda en Almería
---
URL: https://example.com/b
Nombre: Segundo
Temas: inversión
Anchors sugeridos: segundo
"""
    links = parse_allowed_links(raw)
    assert len(links) == 2
    assert links[0]["url"] == "https://example.com/a"
    assert links[0]["anchors"] == ["ejemplo", "vivienda en Almería"]
