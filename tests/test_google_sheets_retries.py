import logging
from unittest.mock import Mock, call

import pytest
from gspread.exceptions import APIError

from src.sheets_client import GoogleSheetsClient, HEADERS, SheetConfigurationError


def api_error(code):
    response = Mock()
    response.json.return_value = {"error": {"code": code, "message": "Fallo simulado"}}
    return APIError(response)


@pytest.fixture
def sheet_setup(tmp_path, monkeypatch):
    credentials = tmp_path / "fake.json"
    credentials.write_text("{}")
    sheet = GoogleSheetsClient("fake-sheet", "Noticias", credentials, logging.getLogger("test"))
    client = Mock()
    worksheet = client.open_by_key.return_value.worksheet.return_value
    worksheet.row_values.return_value = HEADERS
    monkeypatch.setattr("src.sheets_client.gspread.service_account", Mock(return_value=client))
    sleep = Mock()
    monkeypatch.setattr("src.sheets_client.time.sleep", sleep)
    monkeypatch.setattr("src.sheets_client.random.random", lambda: 0.5)
    return sheet, client, worksheet, sleep


def test_open_sheet_recovers_from_service_unavailable(sheet_setup):
    sheet, client, worksheet, sleep = sheet_setup
    spreadsheet = client.open_by_key.return_value
    client.open_by_key.side_effect = [api_error(503), spreadsheet]
    sheet.load_sheet()
    assert sheet.get_headers() == HEADERS
    assert client.open_by_key.call_count == 2
    sleep.assert_called_once_with(1.5)
    worksheet.update.assert_not_called()


def test_persistent_service_failure_stops_before_writes(sheet_setup):
    sheet, client, worksheet, sleep = sheet_setup
    client.open_by_key.side_effect = api_error(503)
    with pytest.raises(SheetConfigurationError, match="503"):
        sheet.load_sheet()
    assert client.open_by_key.call_count == 4
    assert sleep.call_args_list == [call(1.5), call(2.5), call(4.5)]
    worksheet.update.assert_not_called()
    worksheet.batch_update.assert_not_called()


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_permanent_errors_are_not_retried(sheet_setup, code):
    sheet, client, _, sleep = sheet_setup
    client.open_by_key.side_effect = api_error(code)
    with pytest.raises(SheetConfigurationError):
        sheet.load_sheet()
    client.open_by_key.assert_called_once()
    sleep.assert_not_called()


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_row_reads_recover_without_writing(sheet_setup, code):
    sheet, _, worksheet, sleep = sheet_setup
    sheet.load_sheet()
    values = [HEADERS, ["1", "Pendiente", "", "Crear"]]
    worksheet.get_all_values.side_effect = [api_error(code), values]
    assert sheet.find_next_pending_row().row_number == 2
    sleep.assert_called_once_with(1.5)
    worksheet.batch_update.assert_not_called()


def test_failed_write_is_not_retried(sheet_setup):
    sheet, _, worksheet, sleep = sheet_setup
    sheet.load_sheet()
    worksheet.batch_update.side_effect = api_error(503)
    with pytest.raises(RuntimeError, match="503"):
        sheet.update_row_fields(2, {"Estado": "Generando"})
    worksheet.batch_update.assert_called_once()
    sleep.assert_not_called()
