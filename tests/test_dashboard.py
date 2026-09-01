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
    sample_result = [
        {"job_id": "12345", "title": "Software Engineer", "company": "Acme", "result": True, "reason": "submitted", "timestamp": "2026-09-01T10:00:00"}
    ]
    (results_dir / "2026-09-01.json").write_text(json.dumps(sample_result), encoding="utf-8")

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


def test_get_status_endpoint(dashboard_app):
    client = dashboard_app.test_client()
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_processed"] == 1
    assert data["total_submitted"] == 1
    assert data["success_rate_pct"] == 100.0


def test_get_results_endpoint(dashboard_app):
    client = dashboard_app.test_client()
    resp = client.get("/api/results")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["job_id"] == "12345"


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
