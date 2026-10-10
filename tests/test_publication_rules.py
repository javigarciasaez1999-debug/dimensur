import logging
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.automation import EditorialAutomation
from src.models import ApiResult, ImagePlan
from src.settings import load_settings
from src.sheets_client import GoogleSheetsClient, HEADERS
from test_json_builder import generated_content, image_data


@pytest.fixture
def setup_automation(tmp_path, monkeypatch):
    # Simulación de Google Sheets: lectura y escritura solo en memoria.
    values = [list(HEADERS)]
    sheet = GoogleSheetsClient("fake-sheet", "Noticias", tmp_path / "fake.json",
                               logging.getLogger("test"))
    sheet._refresh_header_map(HEADERS)
    sheet.load_sheet = Mock()
    sheet._all_values = Mock(side_effect=lambda: [list(row) for row in values])

    def write(row_number, fields):
        row = values[row_number - 1]
        row.extend([""] * (len(HEADERS) - len(row)))
        for name, value in fields.items():
            row[HEADERS.index(name)] = value

    sheet._write_fields = Mock(side_effect=write)
    shutil.copytree(Path(__file__).resolve().parents[1] / "config", tmp_path / "config")
    automation = EditorialAutomation(load_settings(tmp_path), sheet, logging.getLogger("test"))
    automation._generate_content = Mock(return_value=generated_content())
    automation._plan_image = Mock(return_value=ImagePlan(
        concept="Prueba", prompt="Prueba", alt="Prueba", difference_vs_previous="Prueba"
    ))
    automation._generate_image = Mock(return_value=image_data())
    publish = Mock(return_value=ApiResult(True, 201, "ok", published_url="https://example.test/news"))
    monkeypatch.setattr("src.automation.DimensurApiClient.publish_news", publish)
    return automation, sheet, values, publish


@pytest.mark.parametrize("status", ["crear", "CREAR", " Crear", "Crear ", "Crear\n",
                                   "Crear\t", "Crear\u00a0", "", None,
                                   "Generando", "Subida", "Generado - No publicado", "Error"])
def test_only_exact_crear_is_selected(setup_automation, status):
    _, sheet, values, _ = setup_automation
    values.extend([["1", "Ignorada", "", status], ["2", "Primera válida", "", "Crear"],
                   ["3", "Segunda válida", "", "Crear"]])
    assert sheet.find_next_pending_row().row_number == 3


def test_scheduled_publication_processes_only_first_matching_row(setup_automation):
    automation, sheet, values, publish = setup_automation
    values.extend([["9", "No publicar", "", "crear"],
                   ["8", "Primera por posición, no por ID", "", "Crear"],
                   ["1", "Siguiente semana", "", "Crear"]])
    assert automation.run(dry_run=False, allow_generated_row=False)
    publish.assert_called_once()
    assert sheet.get_row(2).get("Estado") == "crear"
    assert sheet.get_row(3).get("Estado") == "Subida"
    assert sheet.get_row(4).get("Estado") == "Crear"
    assert {call.args[0] for call in sheet._write_fields.call_args_list} == {3}


def test_no_pending_row_is_success_without_writes(setup_automation):
    automation, sheet, values, publish = setup_automation
    values.extend([["1", "Ya publicada", "", "Subida"], ["2", "Espacio", "", "Crear "]])
    assert automation.run(dry_run=False)
    publish.assert_not_called()
    sheet._write_fields.assert_not_called()
    automation._generate_content.assert_not_called()


def test_failure_does_not_continue_to_next_row(setup_automation):
    automation, sheet, values, publish = setup_automation
    values.extend([["1", "Primera", "", "Crear"], ["2", "Segunda", "", "Crear"]])
    publish.return_value = ApiResult(False, 500, "fallo simulado")
    assert not automation.run(dry_run=False)
    publish.assert_called_once()
    assert sheet.get_row(2).get("Estado") == "Error"
    assert sheet.get_row(3).get("Estado") == "Crear"


@pytest.mark.parametrize("new_status", ["Crear ", "crear", "Subida", "Generando"])
def test_status_changed_before_claim_is_not_overwritten(setup_automation, new_status):
    automation, sheet, values, publish = setup_automation
    values.append(["1", "Primera", "", "Crear"])
    original_select = automation._select_row

    def select_then_change(*args):
        row = original_select(*args)
        values[1][3] = new_status
        return row

    automation._select_row = select_then_change
    assert not automation.run(dry_run=False)
    publish.assert_not_called()
    sheet._write_fields.assert_not_called()
    assert sheet.get_row(2).get("Estado") == new_status


def test_dry_run_never_calls_publication_api(setup_automation):
    automation, sheet, values, publish = setup_automation
    values.append(["1", "Prueba", "", "Crear"])
    assert automation.run(dry_run=True)
    publish.assert_not_called()
    assert sheet.get_row(2).get("Estado") == "Generado - No publicado"
