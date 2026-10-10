import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from zoneinfo import ZoneInfo

from main import parse_args

ROOT = Path(__file__).resolve().parents[1]


def workflow(name="dimensur-news.yml"):
    # BaseLoader conserva 'on' como texto, a diferencia del booleano de YAML 1.1.
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def test_single_weekly_schedule_with_madrid_timezone():
    config = workflow()
    assert config["on"]["schedule"] == [{"cron": "0 12 * * 3", "timezone": "Europe/Madrid"}]
    assert set(config["on"]) == {"schedule", "workflow_dispatch"}
    assert config["concurrency"]["cancel-in-progress"] == "false"
    assert config["on"]["workflow_dispatch"]["inputs"]["mode"]["default"] == "dry-run"
    run_step = next(s for s in config["jobs"]["run"]["steps"] if s.get("name") == "Ejecutar automatizacion")
    assert run_step["run"] == "bash scripts/run_github.sh"
    assert "${{" not in run_step["run"]


@pytest.mark.parametrize("day,utc_hour", [("2026-03-25", 11), ("2026-04-01", 10),
                                         ("2026-10-21", 10), ("2026-10-28", 11)])
def test_madrid_noon_before_and_after_dst_changes(day, utc_hour):
    zone = workflow()["on"]["schedule"][0]["timezone"]
    local = datetime.fromisoformat(day + "T12:00:00").replace(tzinfo=ZoneInfo(zone))
    assert local.weekday() == 2
    assert local.astimezone(timezone.utc).hour == utc_hour


@pytest.fixture
def run_script(tmp_path):
    # Sustituye el ejecutable Python; nunca ejecuta main.py ni publica nada.
    fake_python = tmp_path / "python"
    fake_python.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$CAPTURE_ARGS"\n')
    fake_python.chmod(0o755)
    fake_date = tmp_path / "date"
    fake_date.write_text('#!/bin/bash\necho "$FAKE_HOUR"\ntouch "$DATE_USED"\n')
    fake_date.chmod(0o755)

    def run(**overrides):
        args_file = tmp_path / "args"
        env = {"PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
               "CAPTURE_ARGS": str(args_file), "DATE_USED": str(tmp_path / "date-used"),
               "GITHUB_EVENT_NAME": "schedule", "GITHUB_RUN_ATTEMPT": "1",
               "DIMENSUR_API_TOKEN": "test-placeholder", **overrides}
        result = subprocess.run(["bash", str(ROOT / "scripts/run_github.sh")],
                                env=env, text=True, capture_output=True, check=False)
        args = args_file.read_text().splitlines() if args_file.exists() else []
        assert not (tmp_path / "date-used").exists(), "No filtrar por la hora de arranque"
        return result, args
    return run


@pytest.mark.parametrize("hour", ["00", "12", "13", "16", "18", "19", "23"])
def test_schedule_runs_even_if_delayed(run_script, hour):
    result, args = run_script(FAKE_HOUR=hour, INPUT_ROW="999", INPUT_MODE="dry-run")
    assert result.returncode == 0, result.stderr
    assert args == ["main.py", "--publish", "--only-create"]


def test_scheduled_rerun_cannot_consume_another_row(run_script):
    result, args = run_script(GITHUB_RUN_ATTEMPT="2")
    assert result.returncode == 2
    assert args == []


def test_manual_defaults_to_dry_run(run_script):
    result, args = run_script(GITHUB_EVENT_NAME="workflow_dispatch", DIMENSUR_API_TOKEN="")
    assert result.returncode == 0
    assert args == ["main.py", "--dry-run"]


def test_manual_publish_with_explicit_row(run_script):
    result, args = run_script(GITHUB_EVENT_NAME="workflow_dispatch", INPUT_MODE="publish", INPUT_ROW="9")
    assert result.returncode == 0
    assert args == ["main.py", "--publish", "--row", "9"]


@pytest.mark.parametrize("overrides", [
    {"DIMENSUR_API_TOKEN": ""},
    {"GITHUB_EVENT_NAME": "push"},
    {"GITHUB_EVENT_NAME": "workflow_dispatch", "INPUT_MODE": "invalid"},
    {"GITHUB_EVENT_NAME": "workflow_dispatch", "INPUT_ROW": "1"},
    {"GITHUB_EVENT_NAME": "workflow_dispatch", "INPUT_ROW": "2; exit 0"},
])
def test_invalid_execution_fails_before_python(run_script, overrides):
    result, args = run_script(**overrides)
    assert result.returncode == 2
    assert args == []


def test_only_create_cannot_be_bypassed_with_explicit_row(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--publish", "--only-create", "--row", "4"])
    with pytest.raises(SystemExit) as exc:
        parse_args()
    assert exc.value.code == 2


def test_ci_has_no_production_credentials_or_publication_command():
    ci = workflow("tests.yml")
    text = json.dumps(ci)
    assert "secrets." not in text
    assert "main.py" not in text
    assert "--publish" not in text
    assert "python -m pytest -q" in text
