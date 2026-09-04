"""Flask application backend for EasyApply Automator Web Dashboard."""

from __future__ import annotations

import glob
import json
import logging
from pathlib import Path
from typing import Any

import yaml
from flask import Flask, jsonify, render_template, request

from easy_apply_automator.qa.auto_answer import AutoAnswer


def create_dashboard_app(
    config_path: str = "config.yaml",
    qa_path: str = "questions_answers.yaml",
    results_dir: str = "results",
    events_log_path: str = "logs/events.jsonl",
) -> Flask:
    """Factory creating the Flask web dashboard app."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=None,
    )
    # Disable noisy Flask logs for clean terminal output
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

    def _get_qa_data() -> dict[str, Any]:
        p = Path(qa_path)
        if not p.exists():
            example_p = Path("questions_answers.example.yaml")
            if example_p.exists():
                p = example_p
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    return data
        return {"version": 1, "defaults": {}, "profile": {}, "rules": []}

    def _save_qa_data(data: dict[str, Any]) -> None:
        p = Path(qa_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False, allow_unicode=True)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/dates", methods=["GET"])
    def get_dates():
        dates_set = set()
        base_path = Path(results_dir)
        if base_path.exists():
            for p in base_path.iterdir():
                if p.is_dir() and len(p.name) == 10 and p.name.count("-") == 2:
                    dates_set.add(p.name)

        result_files = glob.glob(f"{results_dir}/**/*.json", recursive=True)
        for rf in result_files:
            try:
                stem = Path(rf).stem
                if len(stem) >= 10 and stem[:10].count("-") == 2 and stem[:4].isdigit():
                    dates_set.add(stem[:10])
                else:
                    with open(rf, encoding="utf-8") as f:
                        content = json.load(f)
                        if isinstance(content, list):
                            for item in content[:5]:
                                ts = item.get("timestamp")
                                if ts and len(ts) >= 10 and ts[:10].count("-") == 2:
                                    dates_set.add(ts[:10])
            except Exception:
                continue

        sorted_dates = sorted(dates_set, reverse=True)
        return jsonify({"dates": sorted_dates, "count": len(sorted_dates)})

    @app.route("/api/status", methods=["GET"])
    def get_status():
        date_filter = request.args.get("date", "").strip()
        total_processed = 0
        total_submitted = 0
        total_failed = 0
        latest_timestamp = None
        result_files = sorted(glob.glob(f"{results_dir}/**/*.json", recursive=True))

        for rf in result_files:
            try:
                with open(rf, encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, list):
                        for item in content:
                            ts = item.get("timestamp") or ""
                            if date_filter:
                                item_date = ts[:10] if len(ts) >= 10 else ""
                                file_matches = date_filter in rf.replace("\\", "/")
                                if item_date != date_filter and not file_matches:
                                    continue

                            total_processed += 1
                            if item.get("result"):
                                total_submitted += 1
                            else:
                                total_failed += 1
                            if ts and (latest_timestamp is None or ts > latest_timestamp):
                                latest_timestamp = ts
            except Exception:
                continue

        success_rate = (
            round((total_submitted / total_processed) * 100.0, 1)
            if total_processed > 0
            else 0.0
        )

        return jsonify({
            "status": "online",
            "date": date_filter or None,
            "total_processed": total_processed,
            "total_submitted": total_submitted,
            "total_failed": total_failed,
            "success_rate_pct": success_rate,
            "latest_activity": latest_timestamp,
            "result_files_count": len(result_files),
        })

    @app.route("/api/results", methods=["GET"])
    def get_results():
        limit = int(request.args.get("limit", 200))
        filter_status = request.args.get("status", "").lower()
        search_query = request.args.get("q", "").lower()
        date_filter = request.args.get("date", "").strip()

        jobs = []
        date_submitted = 0
        date_skipped = 0
        result_files = sorted(glob.glob(f"{results_dir}/**/*.json", recursive=True), reverse=True)

        for rf in result_files:
            try:
                with open(rf, encoding="utf-8") as f:
                    items = json.load(f)
                    if isinstance(items, list):
                        for item in items:
                            ts = item.get("timestamp") or ""
                            if date_filter:
                                item_date = ts[:10] if len(ts) >= 10 else ""
                                file_matches = date_filter in rf.replace("\\", "/")
                                if item_date != date_filter and not file_matches:
                                    continue

                            is_submitted = bool(item.get("result"))
                            status_str = "submitted" if is_submitted else "skipped"

                            if is_submitted:
                                date_submitted += 1
                            else:
                                date_skipped += 1

                            if filter_status and filter_status != status_str:
                                continue
                            if search_query:
                                title = (item.get("job_title") or item.get("title") or "").lower()
                                company = (item.get("company") or "").lower()
                                jid = str(item.get("job_id") or "")
                                if (
                                    search_query not in title
                                    and search_query not in company
                                    and search_query not in jid
                                ):
                                    continue

                            jobs.append(item)
                            if len(jobs) >= limit:
                                break
            except Exception:
                continue
            if len(jobs) >= limit:
                break

        return jsonify({
            "jobs": jobs,
            "count": len(jobs),
            "date": date_filter or None,
            "summary": {
                "total": date_submitted + date_skipped,
                "submitted": date_submitted,
                "skipped": date_skipped,
            },
        })

    @app.route("/api/events", methods=["GET"])
    def get_events():
        limit = int(request.args.get("limit", 50))
        events = []
        p = Path(events_log_path)
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in reversed(lines[-limit:]):
                        line_str = line.strip()
                        if line_str:
                            try:
                                events.append(json.loads(line_str))
                            except Exception:
                                pass
            except Exception:
                pass
        return jsonify({"events": events, "count": len(events)})

    @app.route("/api/qa", methods=["GET"])
    def get_qa():
        return jsonify(_get_qa_data())

    @app.route("/api/qa/rule", methods=["POST"])
    def save_qa_rule():
        payload = request.get_json(force=True) or {}
        rule_id = payload.get("id", "").strip()
        patterns = payload.get("match_any", [])
        answer = payload.get("answer", "")

        if not rule_id or not patterns or answer is None:
            return jsonify({"error": "Fields 'id', 'match_any', and 'answer' are required."}), 400

        data = _get_qa_data()
        rules = data.setdefault("rules", [])

        # Check if updating existing rule
        found = False
        for idx, r in enumerate(rules):
            if r.get("id") == rule_id:
                rules[idx] = {
                    "id": rule_id,
                    "match_any": patterns if isinstance(patterns, list) else [patterns],
                    "answer": str(answer),
                }
                found = True
                break

        if not found:
            rules.append({
                "id": rule_id,
                "match_any": patterns if isinstance(patterns, list) else [patterns],
                "answer": str(answer),
            })

        _save_qa_data(data)
        return jsonify({"success": True, "rule_id": rule_id})

    @app.route("/api/qa/rule/<rule_id>", methods=["DELETE"])
    def delete_qa_rule(rule_id: str):
        data = _get_qa_data()
        rules = data.get("rules", [])
        initial_len = len(rules)
        data["rules"] = [r for r in rules if r.get("id") != rule_id]

        if len(data["rules"]) == initial_len:
            return jsonify({"error": f"Rule '{rule_id}' not found."}), 404

        _save_qa_data(data)
        return jsonify({"success": True, "deleted_rule_id": rule_id})

    @app.route("/api/qa/profile", methods=["POST"])
    def update_profile():
        payload = request.get_json(force=True) or {}
        data = _get_qa_data()
        profile = data.setdefault("profile", {})

        if "years" in payload and isinstance(payload["years"], dict):
            profile.setdefault("years", {}).update(payload["years"])
        if "work_auth" in payload and isinstance(payload["work_auth"], dict):
            profile.setdefault("work_auth", {}).update(payload["work_auth"])

        _save_qa_data(data)
        return jsonify({"success": True, "profile": profile})

    @app.route("/api/qa/test", methods=["POST"])
    def test_qa_question():
        payload = request.get_json(force=True) or {}
        question = (payload.get("question") or "").strip()
        if not question:
            return jsonify({"error": "Question field is required"}), 400

        mock_logger = logging.getLogger("qa_test")
        auto_ans = AutoAnswer(
            qa_file=None,
            ans_yaml_path=Path(qa_path),
            salary=str(payload.get("salary", "180000")),
            hourly_rate=str(payload.get("hourly_rate", "150")),
            answers={},
            log=mock_logger,
            full_name="Candidate Full Name",
            first_name="Candidate",
            last_name="Name",
            form_email="candidate@example.com",
            phone_number="+1 555-0199",
            github_url="https://github.com/candidate",
            location_city="New York",
        )

        answer = auto_ans.ans_question(question)
        return jsonify({
            "question": question,
            "answer": answer,
        })

    return app
