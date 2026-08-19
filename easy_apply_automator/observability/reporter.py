"""Automated HTML analytics and session report generator."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any


def generate_html_report(
    output_path: str | Path,
    records: list[dict[str, Any]],
    session_title: str = "EasyApply Automator – Session Report",
) -> Path:
    """Generates a standalone, beautiful HTML dashboard report of application activity."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    total_scanned = len(records)
    applied_count = sum(1 for r in records if r.get("result") is True)
    attempted_count = sum(1 for r in records if r.get("attempted") is True)
    failed_count = sum(1 for r in records if r.get("attempted") is True and not r.get("result"))
    skipped_count = total_scanned - attempted_count
    success_rate = round((applied_count / attempted_count * 100), 1) if attempted_count > 0 else 0.0

    reason_counts: dict[str, int] = {}
    for r in records:
        reason = r.get("reason") or ("submitted" if r.get("result") else "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    rows_html: list[str] = []
    for r in reversed(records):
        ts = html.escape(str(r.get("timestamp", "")))
        job_id = html.escape(str(r.get("job_id", "")))
        title = html.escape(str(r.get("job_title", "Unknown Role")))
        company = html.escape(str(r.get("company", "Unknown Company")))
        result = r.get("result")
        reason = html.escape(str(r.get("reason", "")))
        url = f"https://www.linkedin.com/jobs/view/{job_id}" if job_id else "#"

        if result:
            badge = '<span class="badge badge-success">Applied</span>'
        elif r.get("attempted"):
            badge = f'<span class="badge badge-danger">Failed: {reason}</span>'
        else:
            badge = f'<span class="badge badge-neutral">Skipped: {reason}</span>'

        rows_html.append(
            f"""
            <tr>
                <td>{ts}</td>
                <td><a href="{url}" target="_blank" rel="noopener noreferrer" class="job-link">{title}</a></td>
                <td>{company}</td>
                <td>{badge}</td>
                <td><code>{job_id}</code></td>
            </tr>
            """
        )

    reasons_table_html: list[str] = []
    for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
        reasons_table_html.append(
            f"""
            <tr>
                <td><code>{html.escape(reason)}</code></td>
                <td><strong>{count}</strong></td>
            </tr>
            """
        )

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{session_title}</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-hover: #334155;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --success: #34d399;
            --danger: #f87171;
            --warning: #fbbf24;
            --border: #334155;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            padding: 2rem;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}
        h1 {{ font-size: 1.75rem; font-weight: 700; color: var(--accent); }}
        .timestamp {{ color: var(--text-muted); font-size: 0.9rem; }}
        .grid-kpi {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }}
        .kpi-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }}
        .kpi-num {{
            font-size: 2.25rem;
            font-weight: 800;
            margin-top: 0.25rem;
        }}
        .kpi-label {{
            color: var(--text-muted);
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .text-success {{ color: var(--success); }}
        .text-accent {{ color: var(--accent); }}
        .text-danger {{ color: var(--danger); }}
        .text-warning {{ color: var(--warning); }}
        .text-muted-val {{ color: var(--text-muted); }}
        .section-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }}
        .section-title {{
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--text);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.95rem;
        }}
        th, td {{
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            color: var(--text-muted);
            font-weight: 600;
            background: rgba(0,0,0,0.15);
        }}
        tr:hover td {{
            background: var(--surface-hover);
        }}
        .job-link {{
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }}
        .job-link:hover {{
            text-decoration: underline;
        }}
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .badge-success {{
            background: rgba(52, 211, 153, 0.15);
            color: var(--success);
            border: 1px solid rgba(52, 211, 153, 0.3);
        }}
        .badge-danger {{
            background: rgba(248, 113, 113, 0.15);
            color: var(--danger);
            border: 1px solid rgba(248, 113, 113, 0.3);
        }}
        .badge-neutral {{
            background: rgba(148, 163, 184, 0.15);
            color: var(--text-muted);
            border: 1px solid rgba(148, 163, 184, 0.3);
        }}
        code {{
            background: rgba(0,0,0,0.3);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-size: 0.85rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>EasyApply Automator</h1>
                <div class="timestamp">Session Report generated on {now_str}</div>
            </div>
        </header>

        <div class="grid-kpi">
            <div class="kpi-card">
                <div class="kpi-label">Jobs Scanned</div>
                <div class="kpi-num text-accent">{total_scanned}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Applied & Sent</div>
                <div class="kpi-num text-success">{applied_count}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Attempted</div>
                <div class="kpi-num text-warning">{attempted_count}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Skipped Roles</div>
                <div class="kpi-num text-muted-val">{skipped_count}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Failed Attempts</div>
                <div class="kpi-num text-danger">{failed_count}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Success Rate</div>
                <div class="kpi-num text-success">{success_rate}%</div>
            </div>
        </div>

        <div class="section-card">
            <h2 class="section-title">Application Results</h2>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Position</th>
                            <th>Company</th>
                            <th>Status</th>
                            <th>Job ID</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(rows_html) if rows_html else '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No application records logged yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="section-card">
            <h2 class="section-title">Outcome & Reason Breakdown</h2>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Outcome / Reason</th>
                            <th>Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(reasons_table_html) if reasons_table_html else '<tr><td colspan="2" style="text-align: center; color: var(--text-muted);">No data available.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""
    out.write_text(html_content, encoding="utf-8")
    return out
