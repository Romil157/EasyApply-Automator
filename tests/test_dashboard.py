"""Unit tests for Flask Web Dashboard endpoints."""

from __future__ import annotations

import json

import pytest

from easy_apply_automator.dashboard.server import create_dashboard_app


@pytest.fixture
def dashboard_app(tmp_path):
    qa_file = tmp_path / "questions_answers.yaml"
    qa_file.write_text(
        "version: 1\nprofile:\n  years:\n    python: '2'\ndefaults:\n  unknown_text: 'user provided'\nrules:\n  - id: test_rule\n    match_any:\n      - '(?i)relocate'\n    answer: 'Yes'\n",
        encoding="utf-8",
    )
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    sample_result_1 = [
        {"job_id": "12345", "title": "Software Engineer", "company": "Acme", "result": True, "reason": "submitted", "timestamp": "2026-09-01T10:00:00"}
    ]
    (results_dir / "2026-09-01.json").write_text(json.dumps(sample_result_1), encoding="utf-8")

    sample_result_2 = [
        {"job_id": "99999", "job_title": "Data Analyst", "company": "Global", "result": False, "reason": "skipped", "timestamp": "2026-09-02T15:30:00"}
    ]
    date_dir = results_dir / "2026-09-02"
    date_dir.mkdir()
    (date_dir / "2026-09-02_15-30-00.json").write_text(json.dumps(sample_result_2), encoding="utf-8")

    events_file = tmp_path / "events.jsonl"
    events_file.write_text('{"event_name": "session_start", "timestamp": "2026-09-01T10:00:00"}\n', encoding="utf-8")

    app = create_dashboard_app(
        config_path="config.yaml",
        qa_path=str(qa_file),
        results_dir=str(results_dir),
        events_log_path=str(events_file),
    )
    app.config["TESTING"] = True
    return app


def test_index_route_renders_html(dashboard_app):
    client = dashboard_app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "EasyApply Automator" in resp.get_data(as_text=True)


def test_get_dates_endpoint(dashboard_app):
    client = dashboard_app.test_client()
    resp = client.get("/api/dates")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "dates" in data
    assert "2026-09-02" in data["dates"]
    assert "2026-09-01" in data["dates"]
    assert data["dates"][0] == "2026-09-02"


def test_get_status_endpoint(dashboard_app):
    client = dashboard_app.test_client()
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_processed"] == 2
    assert data["total_submitted"] == 1
    assert data["total_failed"] == 1
    assert data["success_rate_pct"] == 50.0

    # Filtered by date 2026-09-01
    resp_date1 = client.get("/api/status?date=2026-09-01")
    assert resp_date1.status_code == 200
    data1 = resp_date1.get_json()
    assert data1["total_processed"] == 1
    assert data1["total_submitted"] == 1
    assert data1["success_rate_pct"] == 100.0

    # Filtered by date 2026-09-02
    resp_date2 = client.get("/api/status?date=2026-09-02")
    assert resp_date2.status_code == 200
    data2 = resp_date2.get_json()
    assert data2["total_processed"] == 1
    assert data2["total_submitted"] == 0
    assert data2["total_failed"] == 1
    assert data2["success_rate_pct"] == 0.0


def test_get_results_endpoint(dashboard_app):
    client = dashboard_app.test_client()
    resp = client.get("/api/results")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["jobs"]) == 2

    # Filter by date 2026-09-01
    resp_date1 = client.get("/api/results?date=2026-09-01")
    assert resp_date1.status_code == 200
    data1 = resp_date1.get_json()
    assert len(data1["jobs"]) == 1
    assert data1["jobs"][0]["job_id"] == "12345"
    assert data1["summary"]["submitted"] == 1
    assert data1["summary"]["skipped"] == 0

    # Filter by date 2026-09-02
    resp_date2 = client.get("/api/results?date=2026-09-02")
    assert resp_date2.status_code == 200
    data2 = resp_date2.get_json()
    assert len(data2["jobs"]) == 1
    assert data2["jobs"][0]["job_id"] == "99999"
    assert data2["summary"]["submitted"] == 0
    assert data2["summary"]["skipped"] == 1

    # Filter by non-existent date
    resp_empty = client.get("/api/results?date=2026-09-99")
    assert resp_empty.status_code == 200
    data_empty = resp_empty.get_json()
    assert len(data_empty["jobs"]) == 0



def test_get_events_endpoint(dashboard_app):
    client = dashboard_app.test_client()
    resp = client.get("/api/events")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["events"]) == 1
    assert data["events"][0]["event_name"] == "session_start"


def test_qa_crud_and_test_endpoints(dashboard_app):
    client = dashboard_app.test_client()

    # Get QA
    resp = client.get("/api/qa")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "test_rule" in [r["id"] for r in data["rules"]]

    # Test Sandbox
    resp = client.post("/api/qa/test", json={"question": "Are you willing to relocate to Seattle?"})
    assert resp.status_code == 200
    test_data = resp.get_json()
    assert test_data["answer"] == "Yes"

    # Add new rule
    resp = client.post("/api/qa/rule", json={
        "id": "new_salary_rule",
        "match_any": ["(?i)desired compensation"],
        "answer": "$150,000"
    })
    assert resp.status_code == 200

    # Delete rule
    resp = client.delete("/api/qa/rule/new_salary_rule")
    assert resp.status_code == 200
    assert resp.get_json()["deleted_rule_id"] == "new_salary_rule"
