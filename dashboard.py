#!/usr/bin/env python3
"""Entry point to launch EasyApply Automator Web Dashboard."""

from __future__ import annotations

import argparse
import webbrowser

from easy_apply_automator.dashboard.server import create_dashboard_app


def main():
    parser = argparse.ArgumentParser(description="EasyApply Automator Live Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--qa", default="questions_answers.yaml", help="Path to questions_answers.yaml")
    args = parser.parse_args()

    app = create_dashboard_app(config_path=args.config, qa_path=args.qa)
    url = f"http://{args.host}:{args.port}"
    print("\n==================================================")
    print(" EasyApply Automator Control Center")
    print(f" Live Dashboard running at: {url}")
    print("==================================================\n")

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
