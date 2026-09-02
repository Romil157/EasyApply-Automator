"""Automated HTML analytics and session report generator."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def generate_html_report(
    output_path: str | Path,
    records: list[dict[str, Any]],
    session_title: str = "EasyApply Automator – Session Report",
) -> Path:
    """Generates a standalone HTML dashboard report of application activity."""
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

    safe_records: list[dict[str, Any]] = []
    for r in records:
        safe_records.append({
            "timestamp": str(r.get("timestamp", "")),
            "job_id": str(r.get("job_id", "")),
            "job_title": str(r.get("job_title", "Unknown Role")),
            "company": str(r.get("company", "Unknown Company")),
            "attempted": bool(r.get("attempted", False)),
            "result": bool(r.get("result", False)),
            "reason": str(r.get("reason", "submitted" if r.get("result") else "unknown")),
            "location": str(r.get("location", "")),
        })

    records_json_str = json.dumps(safe_records, ensure_ascii=False)
    now_str = datetime.now().strftime("%B %d, %Y • %I:%M:%S %p")

    # Pre-render table rows
    rows_html: list[str] = []
    for r in reversed(safe_records):
        ts = html.escape(str(r["timestamp"]))
        job_id = html.escape(str(r["job_id"]))
        title = html.escape(str(r["job_title"]))
        company = html.escape(str(r["company"]))
        result = bool(r["result"])
        reason = html.escape(str(r["reason"]))
        url = f"https://www.linkedin.com/jobs/view/{job_id}" if job_id else "#"

        if result:
            badge = '<span class="status-badge status-submitted"><span class="pulse-dot green"></span>Applied</span>'
        elif r.get("attempted"):
            badge = f'<span class="status-badge status-failed"><span class="pulse-dot red"></span>Failed ({reason})</span>'
        else:
            badge = f'<span class="status-badge status-skipped"><span class="pulse-dot neutral"></span>Skipped ({reason})</span>'

        company_str = str(r["company"])
        initials = "".join([w[0] for w in company_str.split()[:2]]).upper() or "JB"

        rows_html.append(
            f"""
            <tr class="job-row" data-job-id="{job_id}" data-status="{'submitted' if result else ('failed' if r.get('attempted') else 'skipped')}">
                <td class="col-time">{ts}</td>
                <td class="col-role">
                    <div class="role-cell">
                        <span class="company-avatar">{initials}</span>
                        <div>
                            <a href="{url}" target="_blank" rel="noopener noreferrer" class="role-title">{title}</a>
                            <div class="company-sub">{company}</div>
                        </div>
                    </div>
                </td>
                <td class="col-company">{company}</td>
                <td class="col-status">{badge}</td>
                <td class="col-id"><code>{job_id}</code></td>
                <td class="col-actions">
                    <a href="{url}" target="_blank" rel="noopener noreferrer" class="btn-icon" title="View on LinkedIn">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                    </a>
                </td>
            </tr>
            """
        )

    # Outcome breakdown list
    reasons_list_html: list[str] = []
    total_reasons = sum(reason_counts.values()) or 1
    for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
        pct = round(count / total_reasons * 100, 1)
        reasons_list_html.append(
            f"""
            <div class="reason-row">
                <div class="reason-header">
                    <span class="reason-tag">{html.escape(reason)}</span>
                    <span class="reason-stats"><strong>{count}</strong> <span class="reason-pct">({pct}%)</span></span>
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: {pct}%;"></div>
                </div>
            </div>
            """
        )

    empty_msg = '<tr><td colspan="6" class="empty-state">No application records logged yet. Run a session to view activity.</td></tr>'

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{session_title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #090d16; --surface: rgba(22, 30, 49, 0.75); --border: rgba(255, 255, 255, 0.08);
            --primary: #6366f1; --cyan: #06b6d4; --emerald: #10b981; --amber: #f59e0b; --rose: #f43f5e;
            --text: #f8fafc; --text-sub: #94a3b8; --text-muted: #64748b;
            --radius-md: 12px; --radius-lg: 18px; --shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Plus Jakarta Sans', sans-serif; background: var(--bg-base); color: var(--text);
            min-height: 100vh; padding: 2.5rem 1.5rem 4rem; line-height: 1.5;
            background-image: radial-gradient(circle at 15% 10%, rgba(99,102,241,0.08) 0%, transparent 40%),
                              radial-gradient(circle at 85% 20%, rgba(6,182,212,0.06) 0%, transparent 35%);
        }}
        .dashboard-container {{ max-width: 1360px; margin: 0 auto; }}
        .top-nav {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1.5rem; margin-bottom: 2.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--border); }}
        .brand-group {{ display: flex; align-items: center; gap: 1rem; }}
        .brand-logo {{ width: 44px; height: 44px; border-radius: var(--radius-md); background: linear-gradient(135deg, var(--primary), var(--cyan)); display: flex; align-items: center; justify-content: center; }}
        .brand-title {{ font-size: 1.35rem; font-weight: 800; }}
        .brand-subtitle {{ font-size: 0.8rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }}
        .badge-live {{ display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 9999px; background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); color: var(--emerald); font-size: 0.75rem; font-weight: 600; }}
        .pulse-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
        .pulse-dot.green {{ background: var(--emerald); box-shadow: 0 0 8px var(--emerald); }}
        .pulse-dot.red {{ background: var(--rose); }}
        .pulse-dot.neutral {{ background: var(--text-muted); }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }}
        .kpi-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 1.5rem; box-shadow: var(--shadow); }}
        .kpi-label {{ font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 0.5rem; font-weight: 600; }}
        .kpi-value {{ font-size: 2.2rem; font-weight: 800; }}
        .kpi-value.green {{ color: var(--emerald); }}
        .kpi-value.cyan {{ color: var(--cyan); }}
        .kpi-value.amber {{ color: var(--amber); }}
        .kpi-value.rose {{ color: var(--rose); }}
        .analytics-section {{ display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
        @media (max-width: 900px) {{ .analytics-section {{ grid-template-columns: 1fr; }} }}
        .card-panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 1.5rem; box-shadow: var(--shadow); }}
        .panel-title {{ font-size: 1.05rem; font-weight: 700; margin-bottom: 1.25rem; }}
        .reason-row {{ margin-bottom: 1rem; }}
        .reason-header {{ display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.35rem; }}
        .reason-tag {{ color: var(--text-sub); font-family: 'JetBrains Mono', monospace; }}
        .progress-bar-bg {{ height: 6px; background: rgba(255,255,255,0.06); border-radius: 9999px; overflow: hidden; }}
        .progress-bar-fill {{ height: 100%; background: linear-gradient(90deg, var(--primary), var(--cyan)); border-radius: 9999px; }}
        .table-toolbar {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem; }}
        .search-input {{ background: rgba(15,23,42,0.6); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 0.6rem 1rem; color: var(--text); width: 280px; }}
        .filter-btn-group {{ display: flex; gap: 0.4rem; }}
        .filter-btn {{ background: transparent; border: 1px solid var(--border); color: var(--text-sub); padding: 0.4rem 0.8rem; border-radius: 8px; cursor: pointer; font-size: 0.8rem; }}
        .filter-btn.active {{ background: var(--primary); color: #fff; border-color: var(--primary); }}
        .table-container {{ overflow-x: auto; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow); }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 0.875rem; }}
        th {{ background: rgba(15,23,42,0.8); padding: 1rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; font-size: 0.72rem; letter-spacing: 0.05em; }}
        td {{ padding: 1rem; border-top: 1px solid var(--border); vertical-align: middle; }}
        .role-cell {{ display: flex; align-items: center; gap: 0.75rem; }}
        .company-avatar {{ width: 32px; height: 32px; border-radius: 8px; background: rgba(255,255,255,0.06); display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; color: var(--cyan); }}
        .role-title {{ color: var(--text); text-decoration: none; font-weight: 600; }}
        .role-title:hover {{ color: var(--primary); }}
        .company-sub {{ font-size: 0.78rem; color: var(--text-muted); }}
        .status-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
        .status-submitted {{ background: rgba(16,185,129,0.12); color: var(--emerald); }}
        .status-failed {{ background: rgba(244,63,94,0.12); color: var(--rose); }}
        .status-skipped {{ background: rgba(148,163,184,0.12); color: var(--text-sub); }}
        .btn-icon {{ color: var(--text-muted); text-decoration: none; }}
        .btn-icon:hover {{ color: var(--primary); }}
        .empty-state {{ text-align: center; color: var(--text-muted); padding: 3rem !important; }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <header class="top-nav">
            <div class="brand-group">
                <div class="brand-logo">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
                </div>
                <div>
                    <h1 class="brand-title">EasyApply Automator</h1>
                    <div class="brand-subtitle">Session Intelligence & Analytics Report</div>
                </div>
            </div>
            <div>
                <span class="badge-live"><span class="pulse-dot green"></span> Completed: {now_str}</span>
            </div>
        </header>

        <section class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Total Jobs Evaluated</div>
                <div class="kpi-value cyan">{total_scanned}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Successfully Applied</div>
                <div class="kpi-value green">{applied_count}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Application Success Rate</div>
                <div class="kpi-value {'green' if success_rate >= 50 else 'amber'}">{success_rate}%</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Failed Submissions</div>
                <div class="kpi-value {'rose' if failed_count > 0 else 'green'}">{failed_count}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Pre-Filtered / Skipped</div>
                <div class="kpi-value">{skipped_count}</div>
            </div>
        </section>

        <section class="analytics-section">
            <div class="card-panel">
                <h2 class="panel-title">Session Summary & Funnel</h2>
                <div style="font-size:0.9rem; color:var(--text-sub); line-height:1.6;">
                    Processed <strong>{total_scanned}</strong> total search postings. 
                    <strong>{attempted_count}</strong> advanced to the Easy Apply application flow, resulting in <strong>{applied_count}</strong> successful submissions ({success_rate}% conversion rate).
                </div>
            </div>
            <div class="card-panel">
                <h2 class="panel-title">Outcome Distribution</h2>
                {''.join(reasons_list_html) if reasons_list_html else '<div style="color:var(--text-muted);font-size:0.85rem;">No outcomes recorded.</div>'}
            </div>
        </section>

        <section>
            <div class="table-toolbar">
                <input type="text" id="searchInput" class="search-input" placeholder="Search by role, company, or ID...">
                <div class="filter-btn-group">
                    <button class="filter-btn active" data-filter="all">All ({total_scanned})</button>
                    <button class="filter-btn" data-filter="submitted">Applied ({applied_count})</button>
                    <button class="filter-btn" data-filter="failed">Failed ({failed_count})</button>
                    <button class="filter-btn" data-filter="skipped">Skipped ({skipped_count})</button>
                </div>
            </div>

            <div class="table-container">
                <table id="jobsTable">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Role & Company</th>
                            <th>Company</th>
                            <th>Status</th>
                            <th>Job ID</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="jobsBody">
                        {''.join(rows_html) if rows_html else empty_msg}
                    </tbody>
                </table>
            </div>
        </section>
    </div>

    <script id="recordsData" type="application/json">
        {records_json_str}
    </script>
    <script>
        const searchInput = document.getElementById('searchInput');
        const filterBtns = document.querySelectorAll('.filter-btn');
        const rows = document.querySelectorAll('.job-row');
        let currentFilter = 'all';

        function applyFilter() {{
            const term = (searchInput ? searchInput.value : '').toLowerCase().trim();
            rows.forEach(row => {{
                const status = row.dataset.status;
                const text = row.textContent.toLowerCase();
                const matchStatus = currentFilter === 'all' || status === currentFilter;
                const matchSearch = !term || text.includes(term);
                row.style.display = (matchStatus && matchSearch) ? '' : 'none';
            }});
        }}

        if (searchInput) searchInput.addEventListener('input', applyFilter);
        filterBtns.forEach(btn => {{
            btn.addEventListener('click', () => {{
                filterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentFilter = btn.dataset.filter;
                applyFilter();
            }});
        }});
    </script>
</body>
</html>
"""
    out.write_text(html_content, encoding="utf-8")
    return out
