# EasyApply Automator

[![Python 3.12](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Romil157/EasyApply-Automator/actions/workflows/ci.yml/badge.svg)](https://github.com/Romil157/EasyApply-Automator/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/Coverage-High-green.svg)](#testing)

## Disclaimer

This software is for educational purposes only. LinkedIn's User Agreement prohibits the use of bots or automated tools that scrape or automate activity. Use this software at your own risk. The developers are not responsible for any account restrictions, suspensions, or bans resulting from the use of this tool.

> A robust, clean, and high-performance automation engine to apply to LinkedIn jobs using the **Easy Apply** feature — built with Python and Selenium.

This project is designed as a clean, production-grade automation bot that parses job criteria, performs searches, filters matching positions, automatically handles multi-step form questions using customized YAML rules, and submits applications in seconds.

---

## Key Features

| Feature | Description |
|:---|:---|
| **Stealth Engine** | Integrated `undetected-chromedriver` to bypass bot detection and mimic real browser fingerprints. |
| **Externalized Locators** | Decoupled HTML selectors into `locators.yaml`, allowing for rapid updates without changing source code. |
| **Human-Like Pacing** | Implements Gaussian-jittered pauses and randomized mouse movements to avoid behavioral analysis. |
| **Secure Credentials** | Only enter your email in the CLI; passwords are typed directly on the secure LinkedIn browser window. |
| **Interactive Level Selector** | Startup CLI prompt for filtering **Internship**, **Entry Level**, or **All Levels**. |
| **Strict Job Filtering** | Automatically filters out roles based on experience levels and custom keywords (e.g., medical or database roles). |
| **YAML Auto-Answers** | Powerful regex-based engine to fill text fields, radio buttons, and dropdowns automatically. |
| **Session Persistence** | Safely serializes cookies to `.auth/` to eliminate the need for repeated logins. |
| **One-Click Run (Windows)** | `.bat` script handles environment setup, dependency installation, and execution. |

---

## Tech Stack

* **Core Language:** Python 3.12+
* **Automation Framework:** Selenium + `undetected-chromedriver` (Anti-Detection)
* **HTML Parsing:** BeautifulSoup (Lxml)
* **Configuration:** PyYAML
* **Data Management:** Pandas & JSONL Event Logging
* **Testing:** Pytest + Pytest-Cov

---

## Project Structure

```text
easy-apply-automator/
├── .github/workflows/ci.yml    # CI pipeline
├── easy_apply_automator/       # Core source package
│   ├── app/                    # Orchestrator & runner entrypoints
│   ├── config/                  # YAML parser and schema mapping
│   ├── domain/                 # Clean dataclass architectures
│   ├── infra/                  # Browser factory & session handling
│   ├── observability/          # Event-driven logging & tracers
│   ├── qa/                     # Question parsing & matching service
│   └── services/               # Business logic (Apply Flow, Session, Throughput)
├── tests/                      # Comprehensive Pytest suite
├── config.yaml                 # Job search & filter settings
├── locators.yaml               # Decoupled HTML element selectors
├── questions_answers.yaml       # Auto-answering database
├── easy_apply_bot.py           # Main entry point
└── run.bat / run.sh            # Startup scripts
```

---

## Quick Start

### Option 1: One-Click Run (Windows)
Simply double-click **`run.bat`**. It manages the virtual environment and dependencies automatically.

### Option 2: Manual Installation
```bash
# 1. Clone and enter directory
git clone https://github.com/Romil157/EasyApply-Automator.git
cd EasyApply-Automator

# 2. Setup virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# 3. Install project and dependencies
pip install .
pip install ".[dev]"      # Install testing tools (pytest, ruff, mypy)

# 4. Start the bot
python easy_apply_bot.py
```

---

## Configuration

### Job Search & Filters (`config.yaml`)
Define your targets, locations, and filter out unwanted roles:
```yaml
positions:
  - Software Engineer
  - Python Developer

locations:
  - Remote
  - India

filters:
  database_related: ["sql", "oracle", "mongodb"]
  medical_related: ["healthcare", "clinical", "nurse"]
```

### Auto-Answer Rules (`questions_answers.yaml`)
Map common questions to your personal data using regex:
```yaml
rules:
  - pattern: "years of experience"
    answer: "2"
  - pattern: "authorized to work"
    answer: "Yes"
```

### Element Locators (`locators.yaml`)
If LinkedIn updates its UI, you only need to update this file. No code changes required:
```yaml
next: ["css", "button[aria-label='Continue to next step']"]
submit: ["css", "button[aria-label='Submit application']"]
```

---

## College Presentation Highlights

If showcasing this project, emphasize these **Engineering Decisions**:

1. **Anti-Fingerprinting**: Transitioned from standard Selenium to `undetected-chromedriver` to avoid "Bot Detected" screens by modifying the `cdc_` string in the browser binary.
2. **Decoupled Selectors**: Implemented a `locators.yaml` strategy. This separates "What to find" (data) from "How to find it" (logic), following the Page Object Model (POM) philosophy.
3. **Behavioral Mimicry**: Rather than fixed `time.sleep()`, the bot uses randomized jitter and human-like coordinate offsets for clicks to bypass simple heuristic detectors.
4. **Domain-Driven Design (DDD)**: Separated the application into `Domain` (models), `Infra` (browser/storage), and `Services` (business logic) for high testability and modularity.
5. **Robust QA Engine**: Uses fuzzy regex matching and answer aliases (e.g., "Yes" $\approx$ "True" $\approx$ "1") to handle varying form implementations.

---

## Testing & Quality

The project maintains a high standard of quality with a comprehensive test suite:

```bash
# Run all tests with coverage report
python -m pytest tests/ -v --cov=easy_apply_automator --cov-report=term-missing

# Linting and Type Checking
python -m ruff check .
python -m mypy easy_apply_automator
```
