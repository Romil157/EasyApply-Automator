# EasyApply Automator

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
├── run.bat            # One-click startup script (Windows)
├── easy_apply_bot.py       # Main bot entry point
├── config.yaml          # Job search settings (Keywords, Locations)
├── questions_answers.yaml     # Auto-answering database & matching rules
├── requirements.txt        # Project dependency package index
├── .env.example          # Environment variable template
└── easy_apply_automator/      # Core Python source package
  ├── app/            # Orchestrator & runner entrypoints
  │  ├── orchestrator.py    # Main Selenium/BS4 crawler engine
  │  └── runner.py       # Config parser and CLI prompt loop
  ├── config/          # Configuration parser and schema mapping
  ├── domain/          # Clean dataclass architectures
  ├── infra/           # WebDriver initialization & session handling
  ├── observability/       # Event-driven logging and JSONL tracers
  ├── qa/            # Question parsing and matching service
  └── services/         # Business logic services (Apply flow, Session, Throughput)
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
