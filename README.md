# EasyApply Automator

[![Python 3.12](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Romil157/EasyApply-Automator/actions/workflows/ci.yml/badge.svg)](https://github.com/Romil157/EasyApply-Automator/actions/workflows/ci.yml)

## Disclaimer

This software is for educational purposes only. LinkedIn's User Agreement prohibits the use of bots or automated tools that scrape or automate activity. Use this software at your own risk. The developers are not responsible for any account restrictions, suspensions, or bans resulting from the use of this tool.

> A robust, clean, and high-performance automation engine to apply to LinkedIn jobs using the **Easy Apply** feature — built with Python and Selenium.

This project is designed as a clean, production-grade automation bot that parses job criteria, performs searches, filters matching positions, automatically handles multi-step form questions using customized YAML rules, and submits applications in seconds.

---

## Key Features

| Feature | Description |
|:---|:---|
| **AI Zero-Shot QA Engine** | Integrated zero-shot answering via Google Gemini, OpenAI, Claude, or local Ollama with profile context injection & self-learning local YAML cache. |
| **Bézier Human Simulation** | Cubic Bézier mouse movement curves, keystroke jittering, smooth multi-step scrolling, natural reading pauses, and adaptive circuit-breaker cooldowns. |
| **Control Center Dashboard** | Live glassmorphic web dashboard (`python dashboard.py`) with real-time KPI streaming, processed jobs explorer, live log monitor, and in-browser QA test sandbox. |
| **React 18 / SDUI Resilience** | Synthetic `PointerEvent` + `MouseEvent` click dispatch pipeline, modern SDUI modal containers, combobox/checkbox auto-recovery, and direct `/apply/` fallback. |
| **Stealth Engine** | `undetected-chromedriver` with anti-automation flags (`--disable-blink-features=AutomationControlled`), cookie persistence, and humanized navigation. |
| **Smart Form Answering** | Regex engine + dynamic skill-to-experience extraction + heuristic fallback for recruiter questions. |
| **Multi-Resume Auto-Match**| Automatically selects matching resume based on job title / keywords from configured resume files. |
| **Country Dial-Code Resolver**| Dynamically selects proper phone country dial codes for any ISO country (IN, US, GB, CA, etc.). |
| **Granular Search Filters** | Filter jobs by posted date (`past_24h`, `past_week`, `past_month`), workplace type (Remote/Hybrid/Onsite), and job type. |
| **Interactive & CLI Modes** | Rich CLI with `--dry-run`, `--headless`, `--level`, `--date-posted`, `--max-apps`, and `--remote-only`. |
| **Externalized Locators** | Decoupled HTML selectors into `locators.yaml`, allowing for rapid updates without changing source code. |
| **Hybrid PII Model** | High-sensitivity personal data is sourced from environment variables, never committed to git. |
| **Session Persistence** | Safely serializes cookies to `.auth/` (gitignored) to eliminate the need for repeated logins. |
| **Multi-Option Launcher** | Interactive `run.bat` / `run.sh` menu to launch the bot, open the live web dashboard, or run the test suite. |

---

## Tech Stack

* **Core Language:** Python 3.12+
* **Automation Framework:** Selenium + `undetected-chromedriver` (Anti-Detection)
* **Web Dashboard:** Flask + Modern Glassmorphism Vanilla CSS / JS
* **AI & LLM Providers:** Google Gemini, OpenAI, Anthropic Claude, Local Ollama (REST / standard library)
* **HTML Parsing:** BeautifulSoup (Lxml parser)
* **Configuration:** PyYAML + python-dotenv (YAML files + environment variable overlay)
* **Observability:** Standard `logging` + JSONL event tracing under `logs/`
* **Testing:** Pytest + Pytest-Cov + Ruff + Mypy

---

## Project Structure

```text
easy-apply-automator/
├── .github/workflows/ci.yml        # CI pipeline (ruff, mypy, pytest)
├── easy_apply_automator/           # Core source package
│   ├── app/                        # Orchestrator, runner, and search loop
│   │   ├── orchestrator.py
│   │   ├── runner.py
│   │   └── search_loop.py
│   ├── config/                     # YAML parser + env overlay + RunConfig schema
│   ├── dashboard/                  # Live Web Dashboard & REST API
│   │   ├── server.py               # Flask application & API routes
│   │   └── templates/index.html    # Glassmorphism control center SPA
│   ├── domain/                     # AppConfig / RuntimeConfig / SessionMetrics dataclasses
│   ├── infra/                      # Browser factory, human simulation & result repositories
│   │   ├── browser_factory.py      # Undetected ChromeDriver builder
│   │   ├── human_simulation.py     # Bézier curves, typing jitter & circuit breaker
│   │   └── repositories.py         # File results repository
│   ├── observability/              # Logger setup + JSONL EventLogger
│   ├── qa/                         # AutoAnswer regex + template engine + LLM client
│   │   ├── auto_answer.py          # QA matching & self-learning rule persistence
│   │   └── llm_client.py           # Universal Gemini/OpenAI/Ollama REST client
│   └── services/                   # Business logic & apply flow state machine
│       ├── base.py                 # ServiceBase
│       ├── session_service.py      # Login, cookie save/restore
│       ├── question_service.py     # Question parsing & matching
│       ├── diagnostics_service.py  # Job metadata extraction + debug HTML dumps
│       ├── throughput_service.py   # Submission-rate pacing & short breaks
│       ├── apply_flow_service.py   # Public compose of form-filler + submit-flow mixins
│       ├── _form_filler.py         # Easy Apply required-field filling & recovery
│       └── _submit_flow.py         # Apply-flow state machine + retry/stall handling
├── tests/                          # Pytest suite (200+ unit & mock-based tests)
├── config.yaml                     # Job search & filter settings (tracked)
├── locators.yaml                   # Decoupled HTML element selectors (tracked)
├── questions_answers.example.yaml  # Auto-answer rule template (tracked)
├── questions_answers.yaml           # Your local answer profile (gitignored)
├── .env.example                    # Environment variable template (tracked)
├── .env                            # Your local secrets (gitignored)
├── easy_apply_bot.py               # Main bot CLI entry point
├── dashboard.py                    # Live Web Dashboard launcher
└── run.bat / run.sh                # Startup scripts with interactive menu
```

Runtime artifacts (all gitignored): `.auth/` (cookies), `logs/` (logs + events.jsonl), `debug/` (HTML snapshots), `results/` (per-run application output).

---

## Quick Start

### Option 1: One-Click Interactive Launcher
* **Windows**: Double-click **`run.bat`** (or run `run.bat` in terminal).
* **Linux / macOS**: Run **`./run.sh`**.

The launcher provides an interactive menu:
```text
Choose an action to run:
 [1] Start EasyApply Bot
 [2] Start Live Web Dashboard
 [3] Run Test Suite (pytest)
```

### Option 2: Manual Installation & CLI
```bash
# 1. Clone and enter directory
git clone https://github.com/Romil157/EasyApply-Automator.git
cd EasyApply-Automator

# 2. Setup virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# 3. Install project and dependencies
pip install -e .
pip install ".[dev]"      # Install testing tools (pytest, ruff, mypy)

# 4. Create your local config files from the tracked templates
cp .env.example .env                                # edit .env with your credentials / AI keys
cp questions_answers.example.yaml questions_answers.yaml  # edit with your profile data

# 5. Start the bot or dashboard
python easy_apply_bot.py      # Run bot
python dashboard.py           # Launch Control Center Web Dashboard on http://127.0.0.1:5000
```

---

## Configuration

EasyApply Automator separates configuration into three layers:

1. **`config.yaml`** (tracked) — job search criteria and runtime pacing.
2. **`.env`** (gitignored) — credentials and high-sensitivity PII sourced via environment variables.
3. **`questions_answers.yaml`** (gitignored) — local answer profile: years of experience, demographics, work-authorization answers, education, cover-letter text.

A tracked **template** exists for each gitignored file (`.env.example`, `questions_answers.example.yaml`) so fresh clones still work out of the box — `AutoAnswer` falls back to the template if your local `questions_answers.yaml` is missing, and personal values are then injected from environment variables.

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
  database_related:
    - "sql"
    - "oracle"
    - "mongodb"
  medical_related:
    - "healthcare"
    - "clinical"
    - "nurse"

# Experience level selection happens at startup via the CLI prompt.
# The numeric codes in config.yaml map through an internal remap:
#   1 -> Entry level   |   2 -> Associate   |   6 -> Internship
# The CLI prompt overrides this list at runtime.
experience_level:
  - 1  # Entry level
  - 2  # Associate
  - 6  # Internship
```

### Environment Variables (`.env`)

Environment variables take precedence over `config.yaml` and are the **only** place to store high-sensitivity PII. Copy `.env.example` to `.env` and fill in your values:

| Variable | Purpose |
|:---|:---|
| `LINKEDIN_USERNAME` | Login email (typed into the LinkedIn login page) |
| `LINKEDIN_PASSWORD` | Optional prompt marker; password itself is always typed manually in the browser |
| `LINKEDIN_FULL_NAME` | Full name, injected into `{full_name}` answer templates |
| `LINKEDIN_FIRST_NAME` | First name, injected into `{first_name}` |
| `LINKEDIN_LAST_NAME` | Last name, injected into `{last_name}` |
| `LINKEDIN_EMAIL` | Email, injected into `{form_email}` |
| `LINKEDIN_PHONE_NUMBER` | Phone, injected into `{phone_number}` |
| `LINKEDIN_PROFILE_URL` | LinkedIn profile URL, injected into `{linkedin_profile_url}` |
| `LINKEDIN_GITHUB_URL` | GitHub/portfolio URL, injected into `{github_url}` |
| `LINKEDIN_LOCATION_COUNTRY` | ISO country code (default `IN`) |
| `LINKEDIN_LOCATION_CITY` | City, injected into `{location_city}` |
| `LINKEDIN_SALARY` | Salary expectation, injected into `{salary}` |
| `LINKEDIN_RATE` | Hourly rate expectation, injected into `{hourly_rate}` |
| `EASYAPPLY_IGNORE_CERT_ERRORS` | Set to `1` **only** behind a corporate TLS-intercepting proxy. Disables TLS verification in the browser. Off by default. |

### Auto-Answer Rules (`questions_answers.yaml`)

The answer engine matches each form question against an ordered list of rules. The first rule whose `match_any` regexes hit wins. Answers support `{placeholder}` templating resolved at runtime from env vars and the local profile blocks.

```yaml
version: 1

defaults:
  unknown_years: "0"
  unknown_text: "user provided"
  yes: "Yes"
  no: "No"
  prefer_not: "Wish not to answer"
  no_self_id: "I do not wish to self-identify"

profile:
  years:
    python: "2"
    sql: "1"
  work_auth:
    require_sponsorship: "No"
    legally_authorized: "Yes"
  demographics:
    nationality: "Indian"
    government_id: "I do not wish to self-identify"

rules:
  - id: salary
    match_any:
      - "(?i)salary"
      - "(?i)compensation"
    answer: "{salary}"               # ↳ resolved from LINKEDIN_SALARY

  - id: sponsorship
    match_any:
      - "(?i)require sponsorship"
    answer: "{require_sponsorship}"  # ↳ resolved from profile.work_auth

  - id: python_years
    match_any:
      - "(?i)years of python"
    answer: "{years.python}"         # ↳ resolved from profile.years

  - id: phone_number
    match_any:
      - "(?i)phone"
    answer: "{phone_number}"         # ↳ resolved from LINKEDIN_PHONE_NUMBER

  - id: linkedin_profile
    match_any:
      - "(?i)linkedin profile"
    answer: "{linkedin_profile_url}" # ↳ resolved from LINKEDIN_PROFILE_URL
```

See `questions_answers.example.yaml` for the full rule set (years of experience per skill, common questions, yes/no helpers, etc.). Copy it to `questions_answers.yaml` (gitignored) and fill in your personal values.

If an env var is unset, the corresponding `{placeholder}` is left intact in the rendered answer as a visible signal that the value is missing.

### Element Locators (`locators.yaml`)

If LinkedIn updates its UI, you only need to update this file. No code changes required:

```yaml
next: ["css", "button[aria-label='Continue to next step']"]
submit: ["css", "button[aria-label='Submit application']"]
```

Format: `key: [type, value]` where `type` is one of `css`, `xpath`, `id`, `class`, `name`. Unknown types fall back to CSS.

---

## Runtime Artifacts & Troubleshooting

The bot writes to several gitignored directories at runtime:

| Path | Contents |
|:---|:---|
| `.auth/linkedin_cookies.json` | Session cookies for login reuse (chmod `0600` on POSIX). Delete to force a fresh login. |
| `logs/YYYY-MM-DD_HH-MM-SS_applyJobs.log` | Human-readable run log. |
| `logs/events.jsonl` | Append-only structured event stream (one JSON object per line). Greppable for `event` field. |
| `debug/first_job_<id>_<ts>/` | One-time HTML + metadata snapshot of the first job in a session — used for diagnosing apply-flow breakages. |
| `debug/failed/job_<id>_<ts>/` | HTML + metadata snapshots for jobs that failed mid-apply. |
| `results/<timestamp>.json` | Per-run application outcome file. |

### Common issues

* **Bot keeps trying to log in** — `.auth/linkedin_cookies.json` is missing or expired. Delete it and run again to log in manually; a fresh cookie file will be written on success.
* **`{phone_number}` showing up literally in answer text** — `LINKEDIN_PHONE_NUMBER` env var is unset. Add it to `.env` and restart.
* **A form question wasn't answered** — the question didn't match any rule in `questions_answers.yaml`. Add a new rule under `rules:` with a `match_any` regex and an `answer`. Unmatched questions fall through to `defaults.unknown_text` (`"user provided"`).
* **`debug/` is taking up disk space** — snapshots are written eagerly during apply-flow failures. Safe to delete anytime; the bot will recreate `debug/failed/` on demand.
* **Certificate errors behind a corporate proxy** — set `EASYAPPLY_IGNORE_CERT_ERRORS=1` in `.env`. This disables TLS verification in the browser; only use this on trusted networks.

### Privacy & security checklist

* `.env`, `.auth/`, `logs/`, `debug/`, `results/`, and `questions_answers.yaml` are all gitignored by default — keep them that way.
* Never commit real PII. Use `.env` for high-sensitivity values and treat `questions_answers.yaml` as a local-only file.
* If you've cloned a previous version of this repo that contained committed PII, scrub git history with `git filter-repo --replace-text` and rotate any exposed credentials (LinkedIn password, phone number, etc.).

---

## College Presentation Highlights

If showcasing this project, emphasize these **Engineering Decisions**:

1. **Anti-Fingerprinting**: Transitioned from standard Selenium to `undetected-chromedriver` to avoid "Bot Detected" screens by modifying the `cdc_` string in the browser binary.
2. **Decoupled Selectors**: Implemented a `locators.yaml` strategy. This separates "What to find" (data) from "How to find it" (logic), following the Page Object Model (POM) philosophy.
3. **Behavioral Mimicry**: Rather than fixed `time.sleep()`, the bot uses randomized jitter and human-like coordinate offsets for clicks to bypass simple heuristic detectors.
4. **Domain-Driven Design (DDD)**: Separated the application into `Domain` (models), `Infra` (browser/storage), and `Services` (business logic) for high testability and modularity.
5. **Robust QA Engine**: Uses fuzzy regex matching and answer aliases (e.g., "Yes" $\approx$ "True" $\approx$ "1") to handle varying form implementations.
6. **Hybrid PII Model**: Keeps personal data out of version control by sourcing high-sensitivity fields (name, phone, email, profile URLs) from environment variables while storing lower-sensitivity profile data (years of experience, demographics) in a gitignored local YAML file.

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

The CI pipeline (`.github/workflows/ci.yml`) runs ruff, mypy, and the full pytest suite on every push and pull request.
