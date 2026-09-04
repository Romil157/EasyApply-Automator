from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from easy_apply_automator.infra.repositories import (
    ResultsRepository,
    load_recent_applied_ids,
)


def test_results_repository_append_fresh(tmp_path: Path):
    results_file = tmp_path / "results.json"
    repo = ResultsRepository(str(results_file))

    record = {"job_id": "12345", "title": "Software Engineer", "status": "applied"}
    repo.append(record)

    assert results_file.exists()
    with open(results_file, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["job_id"] == "12345"

    csv_file = tmp_path / "results.csv"
    assert csv_file.exists()
    content = csv_file.read_text(encoding="utf-8-sig")
    assert "job_id" in content
    assert "12345" in content


def test_results_repository_append_multiple(tmp_path: Path):
    results_file = tmp_path / "results.json"
    repo = ResultsRepository(str(results_file))

    repo.append({"job_id": "1", "title": "Dev 1"})
    repo.append({"job_id": "2", "title": "Dev 2"})

    with open(results_file, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 2
    assert data[0]["job_id"] == "1"
    assert data[1]["job_id"] == "2"


def test_results_repository_handles_corrupt_json(tmp_path: Path):
    results_file = tmp_path / "results.json"
    results_file.write_text("{corrupt: [json content without closing", encoding="utf-8")

    repo = ResultsRepository(str(results_file))
    repo.append({"job_id": "999", "title": "Recovered Job"})

    with open(results_file, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["job_id"] == "999"

    # Verify a .corrupt_* backup file was created
    corrupt_backups = list(tmp_path.glob("results.corrupt_*"))
    assert len(corrupt_backups) == 1


def test_load_recent_applied_ids_valid(tmp_path: Path):
    results_file = tmp_path / "results.json"
    now_iso = datetime.now().isoformat()
    results_file.write_text(
        json.dumps([{"job_id": "11111", "timestamp": now_iso, "result": True}]),
        encoding="utf-8",
    )

    ids = load_recent_applied_ids(str(results_file), days=1)
    assert ids is not None
    assert "11111" in ids


def test_load_recent_applied_ids_nonexistent_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    missing_file = tmp_path / "does_not_exist.json"
    ids = load_recent_applied_ids(str(missing_file))
    assert ids is None
