from src.settings import load_settings


def test_google_sheet_url_is_accepted(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    monkeypatch.setenv(
        "GOOGLE_SHEET_URL",
        "https://docs.google.com/spreadsheets/d/abc123DEF/edit?usp=sharing",
    )

    settings = load_settings(tmp_path)

    assert settings.google_sheet_id == "abc123DEF"


def test_google_sheet_id_can_be_full_url(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(
        "GOOGLE_SHEET_ID",
        "https://docs.google.com/spreadsheets/d/xyz789/edit#gid=0",
    )

    settings = load_settings(tmp_path)

    assert settings.google_sheet_id == "xyz789"
