# EasyApply Automator

[![Python 3.12](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Romil157/EasyApply-Automator/actions/workflows/ci.yml/badge.svg)](https://github.com/Romil157/EasyApply-Automator/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/Coverage-14%25-yellow.svg)](#testing)


## Disclaimer

This software is for educational purposes only. LinkedIn's User Agreement prohibits the use of bots or automated tools that scrape or automate activity. Use this software at your own risk. The developers are not responsible for any account restrictions, suspensions, or bans resulting from the use of this tool.

> A robust, clean, and high-performance automation engine to apply to LinkedIn jobs using the **Easy Apply** feature — built with Python and Selenium.

This project is designed as a clean, production-grade automation bot that parses job criteria, performs searches, filters matching positions, automatically handles multi-step form questions using customized YAML rules, and submits applications in seconds.

---

## Key Features

| Feature | Description |
|:---|:---|
| **Ultra-Fast Engine** | Optimized pacing, smart scrolling, and parallel page checks for lightning-fast applications. |
| **Secure Credentials** | Only enter your email in the CLI; passwords are typed directly on the secure LinkedIn browser window to prevent credential leaks. |
| **Interactive Level Selector** | Startup CLI prompt allowing you to select **Internship Only**, **Entry Level & Associate (Other)**, or **All Levels**. |
| **Strict Post-Load Filter** | Automatically verifies job descriptions and metadata post-load to guarantee strict compliance with chosen experience levels. |
| **YAML Auto-Answers** | Custom regex-based auto-answering engine to fill fields, choose options, and upload resumes. |
| **Session Persistence** | Safely serializes and loads session cookies from `.auth/` so you only log in once. |
| **One-Click Run (Windows)** | A fully configured `.bat` script that manages environment initialization, virtual environment creation, pip installations, and execution out-of-the-box. |

---

## Tech Stack

* **Core Language:** Python 3.12+
* **Automation Framework:** Selenium WebDriver (Chrome)
* **HTML Parsing & Extraction:** BeautifulSoup (Lxml)
* **Configuration Parsing:** PyYAML
* **Data Management:** Pandas & JSONL Event Logging

---

## Project Structure

```text
easy-apply-automator/
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions continuous integration pipeline
├── easy_apply_automator/   # Core Python source package
│   ├── app/                # Orchestrator & runner entrypoints
│   │   ├── orchestrator.py # Main Selenium/BS4 crawler engine
│   │   ├── runner.py       # Config parser and CLI prompt loop
│   │   └── search_loop.py  # Crawling state machine & search combination loop
│   ├── config/             # Configuration parser and schema mapping
│   │   ├── loader.py       # YAML parser and environment variables injector
│   │   ├── schema.py       # Config validators and schema parameters
│   │   └── timing.py       # Centralized timing and pause duration constants
│   ├── domain/             # Clean dataclass architectures
│   │   └── models.py       # App configurations, execution and session metrics
│   ├── infra/              # WebDriver initialization & session handling
│   │   ├── browser_factory.py # Chrome/Chromium manager and options builder
│   │   └── repositories.py # Local result storage and caching layer
│   ├── observability/      # Event-driven logging and JSONL tracers
│   │   ├── events.py       # JSONL trace writer and execution tracker
│   │   └── logger.py       # Setup global python log levels and formats
│   ├── qa/                 # Question parsing and matching service
│   │   └── auto_answer.py  # QA selector rules and regex patterns resolver
│   └── services/           # Business logic services (Apply flow, Session, Throughput)
│       ├── _form_filler.py # Internal mixin logic for radio/select/text forms
│       ├── _submit_flow.py # Internal mixin logic for apply loops and timeouts
│       ├── apply_flow_service.py # Mixin composer exposing public API
│       ├── base.py         # Abstract base service injection class
│       ├── diagnostics_service.py # HTML trace logger and debugging snapshots
│       ├── question_service.py # Normalizes text, alias checks, numeric conversion
│       ├── session_service.py # Validates login state and cookie persistence
│       └── throughput_service.py # Breaks Scheduler and application speed limiter
├── tests/                  # Pytest test suite modules
│   ├── conftest.py         # Standard fixtures for temporary files and mocks
│   ├── test_auto_answer.py # YAML pattern resolution and radio click tests
│   ├── test_config_loader.py # Loader priority and missing parameter coverage
│   ├── test_domain_models.py # Dataclass slot constraints and remapping tests
│   ├── test_question_service.py # Pure logical conversions and aliases verification
│   ├── test_session_service.py # Ambiguous URL login states and cookie fallback checks
│   └── test_throughput_service.py # Break intervals, session metrics and timestamp limits
├── .env.example            # Environment variables template
├── config.yaml             # Job search settings (Keywords, Locations)
├── easy_apply_bot.py       # Main bot entry point
├── LICENSE                 # MIT License details
├── pyproject.toml          # Packaging specifications and dependencies
├── questions_answers.yaml  # Auto-answering database & matching rules
├── requirements.txt        # Legacy pip packages layout index
├── run.bat                 # One-click startup script (Windows)
└── run.sh                  # One-click startup script (macOS/Linux)
```

---

## Quick Start

### Option 1: One-Click Run (Windows)

Simply double-click **`run.bat`** in the root directory. The script will automatically:
1. Detect Python on your system
2. Set up a clean virtual environment (`venv/`)
3. Install/upgrade all required packages in `requirements.txt`
4. Run the interactive startup prompt and launch Chrome

### Option 2: Manual Installation

```bash
# 1. Clone the project and navigate to the directory
cd easy-apply-automator

# 2. Create and activate a Python virtual environment
python -m venv venv
venv\Scripts\activate   # On Windows
# source venv/bin/activate # On macOS/Linux

# 3. Install required packages
pip install -r requirements.txt

# 4. Start the bot
python easy_apply_bot.py
```

---

## Interactive Startup & Login Flow

When the bot starts up:

1. **Experience Level Selector**:
  You will see an interactive prompt to filter experience levels:
  ```text
  ==================================================
     SELECT JOB EXPERIENCE LEVEL
  ==================================================
  1 -> Internship Only
  2 -> Entry Level & Associate (Other)
  3 -> All Levels (Internship, Entry Level & Associate)
  ==================================================
  Select option (1, 2, or 3) [Default: 3]: 
  ```
2. **Secure Login**:
  * The terminal will ask for your LinkedIn account email.
  * A secure Chrome browser window will open, pre-filling your email.
  * **You will type your password directly inside the browser window** (never in the console).
  * If LinkedIn triggers a 2FA code (SMS/Email), enter it manually in Chrome.
  * Once logged in, press **Enter** in the terminal to let the bot continue. The bot serializes session cookies under `.auth/` so future runs bypass login completely.

---

## Custom Configuration

### Job Search Settings (`config.yaml`)

Define your targets, locations, and execution boundaries:
```yaml
positions:
 - Software Engineer
 - Python Developer
 - Web Developer

locations:
 - Mumbai
 - Remote

max_pages_per_search: 3
```

### Auto-Answer Rules (`questions_answers.yaml`)

Configure answers matching specific questions. The auto-answering engine uses regex patterns to map form questions to your information:
```yaml
# Examples
rules:
 - pattern: "years of experience"
  answer: "1"
 - pattern: "authorized to work"
  answer: "Yes"
 - pattern: "require sponsorship"
  answer: "No"
```

---

## College Presentation Highlights

If presenting this project for a college demo or showcase, highlight the following:
* **Clean Code Architecture:** Employs domain-driven structure separating scraping services, data mapping, and repository storage.
* **Intelligent Form Completion:** Implements fuzzy regex keyword matching instead of fragile static selectors to answer questions.
* **Anti-Detect Precautions:** Implements human-like mouse jitters, browser viewport scaling, and random coordinate offsets when clicking buttons to lower detection rates.
* **Error Resilience:** Uses debug trace HTML snapshots and detailed event logging under `logs/` for offline telemetry diagnostics.

---

## Outputs & Reports

* **Application Submissions:** Detailed application records (Timestamp, Job ID, Status, Reason) are appended to your results file (`results.json`).
* **Debug Telemetry:** HTML source snapshots are written to `debug/` on error to help debug form structure.
* **Structured Logs:** Events are logged sequentially in `logs/events.jsonl` for offline parsing.

---

## Testing

The project includes a comprehensive unit testing suite using `pytest`. You can run tests, code formatting checks, and type analysis using the commands below:

```bash
# Run pytest tests with code coverage
python -m pytest tests/ -v --cov=easy_apply_automator --cov-report=term-missing


# Run ruff style checks
python -m ruff check easy_apply_automator tests

# Run mypy static type checking
python -m mypy easy_apply_automator --ignore-missing-imports
```

---

## Demo

Here is a visual overview demonstrating the bot in action:

<!-- [DEMO PLACEHOLDER IMAGE] -->
