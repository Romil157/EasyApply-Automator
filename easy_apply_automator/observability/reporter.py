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
    """Generates a standalone, enterprise-grade HTML dashboard report of application activity."""
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

    # Format records for client-side JSON embedding
    safe_records = []
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

    # Pre-render table rows for SEO / no-JS fallback
    rows_html: list[str] = []
    for r in reversed(safe_records):
        ts = html.escape(r["timestamp"])
        job_id = html.escape(r["job_id"])
        title = html.escape(r["job_title"])
        company = html.escape(r["company"])
        result = r["result"]
        reason = html.escape(r["reason"])
        url = f"https://www.linkedin.com/jobs/view/{job_id}" if job_id else "#"

        if result:
            badge = '<span class="status-badge status-submitted"><span class="pulse-dot green"></span>Applied</span>'
        elif r.get("attempted"):
            badge = f'<span class="status-badge status-failed"><span class="pulse-dot red"></span>Failed ({reason})</span>'
        else:
            badge = f'<span class="status-badge status-skipped"><span class="pulse-dot neutral"></span>Skipped ({reason})</span>'

        initials = "".join([w[0] for w in company.split()[:2]]).upper() or "JB"

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

    # Empty state message
    empty_msg = '<tr><td colspan="6" class="empty-state">No application records logged yet. Run a session to view activity.</td></tr>'

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{session_title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #090d16;
            --bg-subtle: #0f172a;
            --surface-card: rgba(22, 30, 49, 0.75);
            --surface-card-hover: rgba(30, 41, 67, 0.85);
            --surface-border: rgba(255, 255, 255, 0.08);
            --surface-border-bright: rgba(255, 255, 255, 0.16);
            --primary: #6366f1;
            --primary-glow: rgba(99, 102, 241, 0.25);
            --accent-cyan: #06b6d4;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #f43f5e;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 18px;
            --radius-full: 9999px;
            --shadow-card: 0 10px 30px -10px rgba(0, 0, 0, 0.5), 0 0 1px 1px rgba(255, 255, 255, 0.05) inset;
            --shadow-glow: 0 0 25px rgba(99, 102, 241, 0.15);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: var(--font-sans);
            background-color: var(--bg-base);
            background-image: 
                radial-gradient(circle at 15% 10%, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 20%, rgba(6, 182, 212, 0.06) 0%, transparent 35%),
                radial-gradient(circle at 50% 80%, rgba(16, 185, 129, 0.04) 0%, transparent 50%);
            background-attachment: fixed;
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2.5rem 1.5rem 4rem;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}

        .dashboard-container {{
            max-width: 1360px;
            margin: 0 auto;
        }}

        /* Header Bar */
        .top-nav {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1.5rem;
            margin-bottom: 2.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--surface-border);
        }}

        .brand-group {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .brand-logo {{
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, #6366f1, #06b6d4);
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.35);
            color: #fff;
        }}

        .brand-info h1 {{
            font-size: 1.5rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            background: linear-gradient(to right, #ffffff, #cbd5e1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .brand-info .live-status {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.82rem;
            color: var(--text-secondary);
            margin-top: 2px;
        }}

        .pulse-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }}
        .pulse-dot.green {{
            background: var(--accent-emerald);
            box-shadow: 0 0 10px var(--accent-emerald);
        }}
        .pulse-dot.red {{
            background: var(--accent-rose);
            box-shadow: 0 0 10px var(--accent-rose);
        }}
        .pulse-dot.neutral {{
            background: var(--text-muted);
        }}

        .header-actions {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex-wrap: wrap;
        }}

        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.6rem 1.1rem;
            font-size: 0.875rem;
            font-weight: 600;
            border-radius: var(--radius-sm);
            border: 1px solid var(--surface-border);
            background: var(--surface-card);
            color: var(--text-primary);
            cursor: pointer;
            transition: all 0.2s ease;
            backdrop-filter: blur(10px);
            text-decoration: none;
        }}

        .btn:hover {{
            background: var(--surface-card-hover);
            border-color: var(--surface-border-bright);
            transform: translateY(-1px);
        }}

        .btn-primary {{
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            border-color: rgba(255, 255, 255, 0.2);
            box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);
        }}
        .btn-primary:hover {{
            background: linear-gradient(135deg, #4f46e5, #4338ca);
            box-shadow: 0 6px 20px rgba(79, 70, 229, 0.45);
        }}

        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }}

        .kpi-card {{
            background: var(--surface-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-lg);
            padding: 1.4rem;
            box-shadow: var(--shadow-card);
            position: relative;
            overflow: hidden;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--surface-border-bright);
        }}

        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, transparent, var(--surface-border-bright), transparent);
        }}

        .kpi-card.highlight::before {{
            background: linear-gradient(90deg, var(--primary), var(--accent-cyan));
        }}

        .kpi-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }}

        .kpi-title {{
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-secondary);
        }}

        .kpi-icon {{
            width: 32px;
            height: 32px;
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.04);
            color: var(--text-secondary);
        }}

        .kpi-value {{
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1.1;
            letter-spacing: -0.03em;
            color: var(--text-primary);
        }}

        .kpi-subtext {{
            margin-top: 0.4rem;
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        .val-emerald {{ color: var(--accent-emerald); }}
        .val-cyan {{ color: var(--accent-cyan); }}
        .val-indigo {{ color: #818cf8; }}
        .val-amber {{ color: var(--accent-amber); }}
        .val-rose {{ color: var(--accent-rose); }}

        /* Analytics Section Layout */
        .analytics-grid {{
            display: grid;
            grid-template-columns: 1fr 340px;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        @media (max-width: 1024px) {{
            .analytics-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .content-card {{
            background: var(--surface-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-lg);
            padding: 1.75rem;
            box-shadow: var(--shadow-card);
        }}

        .card-header-flex {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .card-title {{
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.01em;
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }}

        /* Funnel Progress Section */
        .funnel-container {{
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }}

        .funnel-step {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .funnel-label {{
            width: 140px;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
        }}

        .funnel-bar-wrapper {{
            flex: 1;
            background: rgba(255, 255, 255, 0.04);
            border-radius: var(--radius-full);
            height: 12px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.06);
            position: relative;
        }}

        .funnel-bar-fill {{
            height: 100%;
            border-radius: var(--radius-full);
            transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1);
        }}

        .funnel-count {{
            width: 70px;
            text-align: right;
            font-size: 0.9rem;
            font-weight: 700;
            font-family: var(--font-mono);
        }}

        /* Reasons Breakdown */
        .reason-row {{
            margin-bottom: 1.1rem;
        }}

        .reason-row:last-child {{
            margin-bottom: 0;
        }}

        .reason-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
            margin-bottom: 0.4rem;
        }}

        .reason-tag {{
            font-family: var(--font-mono);
            font-size: 0.8rem;
            background: rgba(255, 255, 255, 0.06);
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            color: #cbd5e1;
        }}

        .reason-stats strong {{
            color: var(--text-primary);
        }}

        .reason-pct {{
            color: var(--text-muted);
            font-size: 0.8rem;
        }}

        .progress-bar-bg {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            height: 6px;
            overflow: hidden;
        }}

        .progress-bar-fill {{
            background: linear-gradient(90deg, #6366f1, #06b6d4);
            height: 100%;
            border-radius: 4px;
        }}

        /* Interactive Filter & Search Bar */
        .table-controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}

        .filter-pills {{
            display: flex;
            background: rgba(255, 255, 255, 0.04);
            padding: 4px;
            border-radius: var(--radius-md);
            border: 1px solid var(--surface-border);
            gap: 4px;
        }}

        .filter-pill {{
            border: none;
            background: transparent;
            color: var(--text-secondary);
            font-family: var(--font-sans);
            font-size: 0.82rem;
            font-weight: 600;
            padding: 0.4rem 0.9rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .filter-pill:hover {{
            color: var(--text-primary);
        }}

        .filter-pill.active {{
            background: var(--primary);
            color: #ffffff;
            box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
        }}

        .search-box {{
            position: relative;
            min-width: 280px;
        }}

        .search-icon {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            pointer-events: none;
        }}

        .search-input {{
            width: 100%;
            padding: 0.55rem 1rem 0.55rem 2.4rem;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-md);
            color: var(--text-primary);
            font-family: var(--font-sans);
            font-size: 0.875rem;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}

        .search-input:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
            background: rgba(255, 255, 255, 0.07);
        }}

        /* Data Table */
        .table-wrapper {{
            overflow-x: auto;
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-md);
            background: rgba(15, 23, 42, 0.4);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }}

        th {{
            background: rgba(255, 255, 255, 0.02);
            color: var(--text-muted);
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            padding: 0.9rem 1.2rem;
            border-bottom: 1px solid var(--surface-border);
            white-space: nowrap;
        }}

        td {{
            padding: 1rem 1.2rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: var(--text-secondary);
            vertical-align: middle;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tbody tr:hover td {{
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-primary);
        }}

        .col-time {{
            font-family: var(--font-mono);
            font-size: 0.82rem;
            white-space: nowrap;
            color: var(--text-muted);
        }}

        .role-cell {{
            display: flex;
            align-items: center;
            gap: 0.85rem;
        }}

        .company-avatar {{
            width: 34px;
            height: 34px;
            border-radius: var(--radius-sm);
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(6, 182, 212, 0.2));
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #e2e8f0;
            font-size: 0.78rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }}

        .role-title {{
            color: var(--text-primary);
            font-weight: 600;
            text-decoration: none;
            transition: color 0.15s;
            display: inline-block;
        }}

        .role-title:hover {{
            color: var(--accent-cyan);
            text-decoration: underline;
        }}

        .company-sub {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 1px;
        }}

        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.3rem 0.75rem;
            border-radius: var(--radius-full);
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            white-space: nowrap;
        }}

        .status-submitted {{
            background: rgba(16, 185, 129, 0.12);
            color: var(--accent-emerald);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .status-failed {{
            background: rgba(244, 63, 94, 0.12);
            color: var(--accent-rose);
            border: 1px solid rgba(244, 63, 94, 0.3);
        }}

        .status-skipped {{
            background: rgba(148, 163, 184, 0.08);
            color: var(--text-secondary);
            border: 1px solid rgba(148, 163, 184, 0.2);
        }}

        code {{
            background: rgba(0, 0, 0, 0.4);
            padding: 0.2rem 0.45rem;
            border-radius: 4px;
            font-size: 0.8rem;
            font-family: var(--font-mono);
            color: #94a3b8;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .btn-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            border-radius: var(--radius-sm);
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--surface-border);
            color: var(--text-secondary);
            transition: all 0.2s ease;
        }}

        .btn-icon:hover {{
            color: var(--text-primary);
            background: var(--surface-card-hover);
            border-color: var(--surface-border-bright);
        }}

        .empty-state {{
            text-align: center;
            padding: 3rem 1rem !important;
            color: var(--text-muted);
            font-size: 0.95rem;
        }}

        /* Toast notification */
        .toast {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #1e293b;
            color: #ffffff;
            padding: 0.75rem 1.25rem;
            border-radius: var(--radius-md);
            border: 1px solid var(--surface-border-bright);
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            font-size: 0.875rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            z-index: 1000;
        }}

        .toast.show {{
            transform: translateY(0);
            opacity: 1;
        }}

        /* Footer */
        footer {{
            margin-top: 3rem;
            text-align: center;
            font-size: 0.82rem;
            color: var(--text-muted);
            border-top: 1px solid var(--surface-border);
            padding-top: 1.5rem;
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- Top Navigation & Brand Header -->
        <header class="top-nav">
            <div class="brand-group">
                <div class="brand-logo">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                </div>
                <div class="brand-info">
                    <h1>EasyApply Automator</h1>
                    <div class="live-status">
                        <span class="pulse-dot green"></span>
                        <span>Session completed • {now_str}</span>
                    </div>
                </div>
            </div>

            <div class="header-actions">
                <button class="btn" id="btn-copy-summary" onclick="copySessionSummary()">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    Copy Summary
                </button>
                <button class="btn" id="btn-export-csv" onclick="exportData('csv')">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    Export CSV
                </button>
                <button class="btn btn-primary" id="btn-export-json" onclick="exportData('json')">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
                    Export JSON
                </button>
            </div>
        </header>

        <!-- Executive Metrics KPI Grid -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-header">
                    <span class="kpi-title">Jobs Scanned</span>
                    <div class="kpi-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    </div>
                </div>
                <div class="kpi-value val-cyan">{total_scanned}</div>
                <div class="kpi-subtext">Discovered from LinkedIn query</div>
            </div>

            <div class="kpi-card highlight">
                <div class="kpi-header">
                    <span class="kpi-title">Applied & Sent</span>
                    <div class="kpi-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                    </div>
                </div>
                <div class="kpi-value val-emerald">{applied_count}</div>
                <div class="kpi-subtext">Submissions successfully completed</div>
            </div>

            <div class="kpi-card">
                <div class="kpi-header">
                    <span class="kpi-title">Attempted</span>
                    <div class="kpi-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                    </div>
                </div>
                <div class="kpi-value val-indigo">{attempted_count}</div>
                <div class="kpi-subtext">Opened application form modal</div>
            </div>

            <div class="kpi-card">
                <div class="kpi-header">
                    <span class="kpi-title">Skipped Roles</span>
                    <div class="kpi-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </div>
                </div>
                <div class="kpi-value val-amber">{skipped_count}</div>
                <div class="kpi-subtext">Filtered by criteria & blacklist</div>
            </div>

            <div class="kpi-card">
                <div class="kpi-header">
                    <span class="kpi-title">Success Rate</span>
                    <div class="kpi-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                    </div>
                </div>
                <div class="kpi-value val-emerald">{success_rate}%</div>
                <div class="kpi-subtext">Applied / Attempted conversions</div>
            </div>
        </div>

        <!-- Funnel and Reason Analysis Grid -->
        <div class="analytics-grid">
            <div class="content-card">
                <div class="card-header-flex">
                    <h2 class="card-title">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"></path></svg>
                        Application Pipeline Funnel
                    </h2>
                    <span style="font-size: 0.8rem; color: var(--text-muted);">Conversion breakdown</span>
                </div>
                <div class="funnel-container">
                    <div class="funnel-step">
                        <div class="funnel-label">1. Scanned Roles</div>
                        <div class="funnel-bar-wrapper">
                            <div class="funnel-bar-fill" style="width: 100%; background: linear-gradient(90deg, #6366f1, #818cf8);"></div>
                        </div>
                        <div class="funnel-count">{total_scanned}</div>
                    </div>
                    <div class="funnel-step">
                        <div class="funnel-label">2. Criteria Matched</div>
                        <div class="funnel-bar-wrapper">
                            <div class="funnel-bar-fill" style="width: {round(attempted_count / (total_scanned or 1) * 100, 1)}%; background: linear-gradient(90deg, #06b6d4, #38bdf8);"></div>
                        </div>
                        <div class="funnel-count">{attempted_count}</div>
                    </div>
                    <div class="funnel-step">
                        <div class="funnel-label">3. Completed & Sent</div>
                        <div class="funnel-bar-wrapper">
                            <div class="funnel-bar-fill" style="width: {round(applied_count / (total_scanned or 1) * 100, 1)}%; background: linear-gradient(90deg, #10b981, #34d399);"></div>
                        </div>
                        <div class="funnel-count">{applied_count}</div>
                    </div>
                </div>
            </div>

            <div class="content-card">
                <div class="card-header-flex">
                    <h2 class="card-title">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                        Outcome Distribution
                    </h2>
                </div>
                <div class="reasons-container">
                    {"".join(reasons_list_html) if reasons_list_html else '<div class="empty-state">No outcome data available.</div>'}
                </div>
            </div>
        </div>

        <!-- Applications Activity Table Section -->
        <div class="content-card">
            <div class="table-controls">
                <div class="filter-pills">
                    <button class="filter-pill active" onclick="setFilter('all', this)">All ({total_scanned})</button>
                    <button class="filter-pill" onclick="setFilter('submitted', this)">Applied ({applied_count})</button>
                    <button class="filter-pill" onclick="setFilter('skipped', this)">Skipped ({skipped_count})</button>
                    <button class="filter-pill" onclick="setFilter('failed', this)">Failed ({failed_count})</button>
                </div>

                <div class="search-box">
                    <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <input type="text" id="table-search" class="search-input" placeholder="Search roles, companies, IDs..." oninput="handleSearch(this.value)">
                </div>
            </div>

            <div class="table-wrapper">
                <table id="applications-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Role & Organization</th>
                            <th>Company</th>
                            <th>Status</th>
                            <th>Job ID</th>
                            <th style="text-align: right;">Action</th>
                        </tr>
                    </thead>
                    <tbody id="table-body">
                        {"".join(rows_html) if rows_html else empty_msg}
                    </tbody>
                </table>
            </div>
        </div>

        <footer>
            EasyApply Automator Analytics &bull; Designed for rapid job search automation &bull; Generated locally
        </footer>
    </div>

    <!-- Toast Notification Element -->
    <div id="toast" class="toast">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
        <span id="toast-text">Notification</span>
    </div>

    <!-- Client-side Interactive Logic -->
    <script id="records-data" type="application/json">
        {records_json_str}
    </script>
    <script>
        const rawRecords = JSON.parse(document.getElementById('records-data').textContent || '[]');
        let currentFilter = 'all';
        let searchQuery = '';

        function setFilter(filterType, elem) {{
            currentFilter = filterType;
            document.querySelectorAll('.filter-pill').forEach(el => el.classList.remove('active'));
            if (elem) elem.classList.add('active');
            renderFilteredRows();
        }}

        function handleSearch(query) {{
            searchQuery = query.toLowerCase().trim();
            renderFilteredRows();
        }}

        function renderFilteredRows() {{
            const rows = document.querySelectorAll('#table-body tr.job-row');
            let visibleCount = 0;

            rows.forEach(row => {{
                const status = row.getAttribute('data-status');
                const text = row.innerText.toLowerCase();

                const matchesStatus = (currentFilter === 'all') || (status === currentFilter);
                const matchesSearch = !searchQuery || text.includes(searchQuery);

                if (matchesStatus && matchesSearch) {{
                    row.style.display = '';
                    visibleCount++;
                }} else {{
                    row.style.display = 'none';
                }}
            }});
        }}

        function showToast(msg) {{
            const toast = document.getElementById('toast');
            const text = document.getElementById('toast-text');
            text.textContent = msg;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }}

        function copySessionSummary() {{
            const summary = `🚀 EasyApply Automator Session Summary\\n` +
                `• Jobs Scanned: {total_scanned}\\n` +
                `• Applied & Sent: {applied_count}\\n` +
                `• Attempted: {attempted_count}\\n` +
                `• Skipped: {skipped_count}\\n` +
                `• Success Rate: {success_rate}%\\n` +
                `• Generated at: {now_str}`;
            navigator.clipboard.writeText(summary).then(() => {{
                showToast('Summary copied to clipboard!');
            }}).catch(() => {{
                showToast('Failed to copy to clipboard');
            }});
        }}

        function exportData(format) {{
            if (!rawRecords.length) {{
                showToast('No records to export');
                return;
            }}

            if (format === 'json') {{
                const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(rawRecords, null, 2));
                const dlAnchorElem = document.createElement('a');
                dlAnchorElem.setAttribute("href", dataStr);
                dlAnchorElem.setAttribute("download", "easyapply_session_records.json");
                dlAnchorElem.click();
                showToast('Exported JSON successfully!');
            }} else if (format === 'csv') {{
                const keys = Object.keys(rawRecords[0] || {{}});
                let csvContent = keys.join(",") + "\\n";
                rawRecords.forEach(r => {{
                    const row = keys.map(k => '"' + (String(r[k] || '')).replace(/"/g, '""') + '"');
                    csvContent += row.join(",") + "\\n";
                }});
                const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
                const link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.setAttribute("download", "easyapply_session_records.csv");
                link.click();
                showToast('Exported CSV successfully!');
            }}
        }}
    </script>
</body>
</html>
"""
    out.write_text(html_content, encoding="utf-8")
    return out
