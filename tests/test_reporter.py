"""Unit tests for HTML Analytics & Session Reporter."""

from __future__ import annotations

import tempfile
from pathlib import Path

from easy_apply_automator.observability.reporter import generate_html_report


class TestGenerateHtmlReport:
    def test_generate_html_report_creates_file_and_contains_kpi(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "test_report.html"
            sample_records = [
                {
                    "timestamp": "2026-08-19 10:00:00",
                    "job_id": "123456",
                    "job_title": "Senior Python Engineer",
                    "company": "Tech Corp",
                    "attempted": True,
                    "result": True,
                    "reason": "submitted",
                },
                {
                    "timestamp": "2026-08-19 10:05:00",
                    "job_id": "789012",
                    "job_title": "Machine Learning Engineer",
                    "company": "AI Labs",
                    "attempted": True,
                    "result": False,
                    "reason": "apply_flow_failed",
                },
                {
                    "timestamp": "2026-08-19 10:10:00",
                    "job_id": "345678",
                    "job_title": "Doctor",
                    "company": "Health Clinic",
                    "attempted": False,
                    "result": False,
                    "reason": "medical_related_title",
                },
            ]

            res_path = generate_html_report(out_file, sample_records)
            assert res_path.exists()

            content = res_path.read_text(encoding="utf-8")
            assert "EasyApply Automator" in content
            assert "Senior Python Engineer" in content
            assert "Tech Corp" in content
            assert "50.0%" in content  # Success rate: 1 applied out of 2 attempted = 50%
            assert "123456" in content
            assert "https://www.linkedin.com/jobs/view/123456" in content

    def test_generate_html_report_empty_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "empty_report.html"
            res_path = generate_html_report(out_file, [])
            assert res_path.exists()
            content = res_path.read_text(encoding="utf-8")
            assert "No application records logged yet." in content
