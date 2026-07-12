import logging

from openpyxl import Workbook

from src.sheets_client import ExcelSheetsClient, HEADERS


def test_excel_backend_creates_template_and_updates_row(tmp_path) -> None:
    path = tmp_path / "noticias.xlsx"
    client = ExcelSheetsClient(path, "Noticias", logging.getLogger("test"))
    client.load_sheet()
    assert client.get_headers() == HEADERS

    worksheet = client.worksheet
    worksheet.append(["1", "Título", "", "Crear"])
    client.workbook.save(path)

    row = client.find_next_pending_row()
    assert row is not None
    assert row.row_number == 2
    client.update_row_status(2, "Generando")
    assert client.get_row(2).get("Estado") == "Generando"


def test_excel_backend_accepts_existing_dimensur_headers(tmp_path) -> None:
    path = tmp_path / "noticias.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Hoja 1"
    worksheet.append(
        [
            "Titulos de contenidos",
            "Contenido",
            "Estado",
            "título",
            "metadescripcion",
            "Imagen a usar",
            "Post ID",
        ]
    )
    worksheet.append(
        [
            "Comprar vivienda",
            "<p>Contenido previo.</p>",
            "Subida",
            "Comprar vivienda en Almería",
            "Descripcion previa",
            "https://example.com/image.jpg",
            "123",
        ]
    )
    worksheet.append(["Nueva noticia", "", "Crear"])
    workbook.save(path)

    client = ExcelSheetsClient(path, "Hoja 1", logging.getLogger("test"))
    client.load_sheet()

    client.require_headers()
    assert client.find_next_pending_row().get("Título base") == "Nueva noticia"
    assert client.get_last_published_article()["title"] == "Comprar vivienda"
