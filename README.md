# EasyApply Automator

<div align="center">

[![Python 3.12](https://img.shields.io/badge/python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI Tests](https://img.shields.io/badge/Tests-277%2B%20Passed-brightgreen.svg)](tests/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)
[![AI Engine: Groq / Gemini / Claude](https://img.shields.io/badge/AI%20Engine-Groq%20%7C%20Gemini%20%7C%20Claude-orange.svg)](easy_apply_automator/qa/)

**Stealth, AI-powered automation engine and real-time control center for LinkedIn Easy Apply.**

[Key Features](#key-features) • [System Architecture](#system-architecture) • [Smart Decision Pipeline](#smart-decision-pipeline) • [Quick Start](#quick-start) • [Web Dashboard](#live-web-dashboard--qa-studio) • [Configuration](#configuration) • [Engineering Highlights](#engineering-decisions--presentation-highlights)

</div>

---

## Disclaimer

> **Educational & Research Purpose Only.**  
> LinkedIn's User Agreement strictly prohibits unauthorized automation, scraping, or botting. Use this software responsibly and at your own risk. The developers assume no liability for account warnings, restrictions, or suspensions resulting from automated activity.

---

## Key Features

### 1. Resilient Job Discovery & SDUI Navigation Support
* **Multi-Selector Card Discovery**: Resiliently scrapes job cards across varying LinkedIn search layouts (`data-job-id`, `data-occludable-job-id`, `div.job-card-container`, `li.jobs-search-results__list-item`, and regex `/jobs/view/(\d+)` anchor parsing) to ensure no listings are missed during DOM restructuring.
* **Server-Driven UI (SDUI) Flow Handling**: Fully supports LinkedIn's modern SDUI navigation-based apply flow (`<a href="...?openSDUIApplyFlow=true">` and dedicated `/apply/` URLs) alongside traditional client-side modal dialogs.
* **Post-Navigation Page Synchronization**: Detects link-triggered page transitions, awaiting DOM readiness and scrolling new application pages before engaging form controls.
* **Resilient Multi-Strategy Fallback**: Direct `/apply/` URL navigation and collection redirect recovery when in-page modal dialogs do not render.

### 2. Resume Relevance Scoring & Pre-Click Search Filtering
* **Search Result Card Pre-Filter**: Scrapes and checks job titles directly from LinkedIn search result cards before clicking into the job page. Blacklisted and low-relevance roles are skipped in under 0.1 seconds without loading or scrolling the full page.
* **Resume-Aligned Relevance Scorer**: Zero-cost heuristic scoring engine (`RelevanceScorer`) matching 60+ technical skills (Software, Python, Flask, Node.js, SQL, Data Scraping, Cybersecurity, SIEM, IT Support, AI/ML, NLP, Automation, QA, Finance, SEO) and blocking 40+ irrelevant categories (non-English language roles, video/reels creation, healthcare, manual labor, sales).
* **Empty Page Fast Exit**: Automatically detects when a search keyword or location yields no more listings after consecutive empty pages, terminating the combo early to avoid burning redundant pagination requests.

### 3. External ATS Redirect & Modal Detection
* **External ATS Early Exit**: Automatically detects when an Easy Apply button redirects to external portals (Workday, Greenhouse, Lever, SmartRecruiters, Ashby, iCIMS, Taleo) within 1-2 seconds, exiting early and returning to LinkedIn without wasting 30+ seconds waiting for non-existent modals.
* **Stealth Single-Click Dispatcher**: Uses randomized single-click strategies (`ActionChains`, direct interaction, or script execution) with humanized pause variance, eliminating synthetic multi-click patterns that trigger anti-bot protections.

### 4. Smart Deduplication, Session Persistence & Atomic Storage
* **Automatic Session Persistence**: Seamlessly caches LinkedIn authentication cookies to `.auth/linkedin_cookies.json` upon successful login, eliminating the need to solve verification challenges on every session run.
* **Atomic Storage & Self-Healing Data Recovery**: Protects `results.json` and CSV reports from truncation or sudden termination crashes using atomic write swaps (`.tmp` + rename). Automatically detects and recovers from corrupted JSON by archiving faulty state (`.corrupt_*`) and cleanly initializing.
* **Non-Destructive Failure Handling**: Distinguishes permanent job skips (already applied, title blacklist, medical filters, low relevance) from transient execution issues (modal timeouts, network stalls). Transient failures remain eligible for subsequent passes instead of being permanently locked out.
* **Multi-Day Cache Ingestion**: Intelligently loads prior successful submissions while preserving uncompleted applications across separate runs.

### 5. AI Zero-Shot Question Answering & Numeric Precision
* **Universal Multi-Provider AI Client**: Native REST client supporting **Groq** (`openai/gpt-oss-120b`, `llama-3.3-70b`), **Google Gemini Flash**, **OpenAI**, **Anthropic Claude**, and **local Ollama** without heavy third-party SDK dependencies.
* **Numeric Answer Precision**: Accurately preserves `0` and `0.0` values for years of experience and numerical questions (preventing zero-experience candidates from being mischaracterized with 1+ years).
* **Prompt Injection Defense & Sanitization**: Strips non-printable control characters and enforces length limits with XML boundary encapsulation on recruiter questions before sending to LLMs.
* **Job-Specific Prompt Enrichment**: Injects the active job title, hiring company, candidate background profile, and `resume.md` into zero-shot prompts, generating customized answers for questions like "Why are you interested in this role?".
* **Self-Learning Local Cache**: When AI resolves an unknown question, it dynamically appends the rule into your local `questions_answers.yaml` on disk. Future occurrences are resolved locally with zero API calls and zero latency.

### 6. Anti-Detection & Human Simulation
* **Cubic Bezier Mouse Trajectories**: Generates randomized cubic Bezier cursor paths with human velocity profiles and subtle overshoot corrections instead of robotic straight-line jumps.
* **Human Keystroke Jitter (`human_type_with_jitter`)**: Emulates human typing cadence with variable inter-keystroke intervals (20ms-65ms) and natural punctuation pauses across all form inputs and contact fields.
* **Natural Smooth Scrolling & Reading Pauses**: Injects multi-step eased scrolling and realistic page reading pauses before interacting with application forms.
* **Progressive Circuit Breaker**: Monitors consecutive failure bursts and triggers escalating cooldown intervals (60s, 120s, 180s up to 300s) to protect accounts from rate limiting, gradually recovering cooldown thresholds as successful submissions resume.
* **Stealth Chrome Flags**: Built-in `--disable-blink-features=AutomationControlled` and persistent user profile support to evade heuristic bot detection.

### 7. Automated Contact Pre-Filling & SDUI Form Recovery
* **Full Contact Field Pre-Filling**: Automatically fills Mobile Phone, Email, First Name, Last Name, City, LinkedIn Profile URL, and GitHub Portfolio with natural typing jitter on initial form pages.
* **Smart Form Auto-Recovery**: Automatically resolves unselected comboboxes, typeahead dropdowns, required legal checkboxes, and multi-option radio groups.

### 8. Live Web Dashboard, Telemetry & Storage Management
* **Glassmorphic Single-Page Application**: Real-time control center (`python dashboard.py`) featuring live KPI streaming (Applications Submitted, Failed, Jobs Evaluated, Submission Rate).
* **Session Performance Telemetry**: Outputs structured summary reports at session completion (duration, attempts, submissions, failure rates, termination reasons).
* **Automated Storage Management**: Automatically prunes older debug HTML failure snapshots on startup to keep disk consumption capped.

---

## System Architecture

```text
+----------------------------------------------------------------------------------+
|                             EasyApply Automator Core                             |
+--------------------------+--------------------------+----------------------------+
|   Application Layer      |     Services Layer       |   Infrastructure Layer     |
|  +--------------------+  |  +--------------------+  |  +----------------------+  |
|  | Orchestrator /     |  |  | Apply Flow State   |  |  | Undetected Browser   |  |
|  | Search Loop        |--|  | Machine & ATS Gate |  |  | Factory (Chrome)     |  |
|  +--------------------+  |  +--------------------+  |  +----------------------+  |
|            |             |            |             |            |               |
|  +--------------------+  |  +--------------------+  |  +----------------------+  |
|  | Live Control       |  |  | Form Filler /      |  |  | Human Simulation:    |  |
|  | Dashboard Server   |  |  | SDUI Recovery      |  |  | Bezier & Jitter      |  |
|  +--------------------+  |  +--------------------+  |  +----------------------+  |
+------------+--------------------------+--------------------------+---------------+
             |                          |                          |
   +-------------------+      +-------------------+      +-------------------+
   | questions_answers |      | Groq / Gemini /   |      | JSONL Telemetry & |
   | Local YAML Rules  |      | Claude LLM Engine |      | Cookie Repository |
   +-------------------+      +-------------------+      +-------------------+
```

---

## Smart Decision Pipeline

```mermaid
flowchart TD
    A[Search Results Page Loaded] --> B[Extract Visible Card Titles]
    B --> C{Card Title Blacklisted?}
    C -- Yes --> S1[Skip Job\n0.1s - No Page Load]
    C -- No --> D{Relevance Score >= 0.15?}
    D -- No --> S2[Skip Job\n0.1s - No Page Load]
    D -- Yes --> E[Load Full Job Page]
    E --> F{External ATS Redirect?}
    F -- Yes --> S3[Early Exit & Return\n1-2s]
    F -- No --> G[Click Easy Apply]
    G --> H{Modal Detected?}
    H -- No --> S4[Fast Retry & Return]
    H -- Yes --> I[Pre-Fill Contact Fields]
    I --> J[Form Step Loop]
    J --> K{Question Match in YAML?}
    K -- Yes --> L[Apply YAML / Regex Rule\n0 API Calls]
    K -- No --> M{Dynamic Skill Pattern?}
    M -- Yes --> N[Extract Years from profile.years]
    M -- No --> O{Recruitment Heuristic?}
    O -- Yes --> P[Contextual Answer\ne.g., Notice Period, Relocation]
    O -- No --> Q{AI Engine Configured?}
    Q -- Yes --> R[Zero-Shot LLM Call\n+ Job Target & resume.md]
    R --> S[Persist Rule to YAML\nSelf-Learning Cache]
    Q -- No --> T[Default Fallback\ne.g., 1 / user provided]
    L --> U[Review & Submit Application]
    N --> U
    P --> U
    S --> U
    T --> U
```

---

## Quick Start

### Option 1: One-Click Interactive Launcher
* **Windows**: Double-click **`run.bat`** (or run `run.bat` in CMD / PowerShell).
* **Linux / macOS**: Run **`./run.sh`**.

The launcher provides an interactive menu for operation mode and target role level:
```text
============================================
   EasyApply Automator - Control Center
============================================

Choose an option to run:
  [1] Start EasyApply Bot
  [2] Start Live Web Dashboard
  [3] Run Pytest Suite

Enter choice 1, 2, or 3 (default 1): 1

Select Target Experience Level:
  [1] Internship Roles Only
  [2] Full-Time & Entry-Level Roles
  [3] All Opportunities (Default)
  [4] Keep config.yaml Settings
```

### Option 2: Manual Installation & CLI
```bash
# 1. Clone the repository
git clone https://github.com/Romil157/EasyApply-Automator.git
cd EasyApply-Automator

# 2. Set up virtual environment
python -m venv venv
source venv/bin/activate  # Linux / macOS
venv\Scripts\activate     # Windows

# 3. Install in editable mode with dev dependencies
pip install -e ".[dev]"

# 4. Copy configuration templates
cp .env.example .env
cp questions_answers.example.yaml questions_answers.yaml

# 5. Start the bot or web dashboard
python easy_apply_bot.py      # Run LinkedIn bot
python dashboard.py           # Launch Web Control Center on http://127.0.0.1:5000
```

---

## Live Web Dashboard & QA Studio

Launch the dashboard at any time to monitor your applications or test QA rules:
```bash
python dashboard.py --port 5000
```

```text
==================================================
 EasyApply Automator Control Center
 Live Dashboard running at: http://127.0.0.1:5000
==================================================
```

### Dashboard Capabilities:
* **Real-Time KPIs**: Total evaluated jobs, successful submissions, failure rates, and live pacing speed.
* **Applications Table**: Searchable history of applied jobs with direct links, timestamps, and error diagnostics.
* **Live Event Stream**: Real-time event log viewer updating automatically as the bot navigates.
* **QA Testing Studio**: Type any recruiter question into the in-browser sandbox to preview the resolved answer.

---

## Configuration

EasyApply Automator follows a clean **3-layer configuration architecture**:

```text
+-------------------------------------------------------------+
| 1. config.yaml (Tracked)                                    |
|    Search positions, locations, filters & date range        |
+-------------------------------------------------------------+
| 2. .env (Gitignored)                                        |
|    Credentials, phone, email, API keys (Groq/Gemini)        |
+-------------------------------------------------------------+
| 3. questions_answers.yaml & resume.md (Gitignored)          |
|    Candidate experience years, custom rules, resume text    |
+-------------------------------------------------------------+
```

### 1. `.env` (Secrets & Personal Data)
Copy `.env.example` to `.env` and fill in your details:

```env
# LinkedIn Credentials
LINKEDIN_USERNAME=your_email@example.com
LINKEDIN_PASSWORD=

# Personal Info Auto-filled in Forms
LINKEDIN_FULL_NAME=Your Full Name
LINKEDIN_FIRST_NAME=Your First Name
LINKEDIN_LAST_NAME=Your Last Name
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PHONE_NUMBER=1234567890
LINKEDIN_LOCATION_COUNTRY=IN
LINKEDIN_LOCATION_CITY=Mumbai
LINKEDIN_SALARY=1000000

# AI / LLM Auto-Answer Engine (Groq / Gemini / OpenAI / Claude)
GROQ_API_KEY=gsk_your_groq_api_key_here
AI_PROVIDER=groq
AI_MODEL=openai/gpt-oss-120b
AI_AUTO_LEARN=1
```

### 2. `config.yaml` (Job Search & Criteria)
```yaml
positions:
  - "Software Engineer"
  - "Python Developer"
  - "Backend Developer"
  - "Data Analyst"
  - "Data Engineer"
  - "Cybersecurity Analyst"
  - "IT Support"
  - "Financial Analyst"
  - "SEO Intern"

locations:
  - Remote
  - Mumbai
  - India
  - Bengaluru

workplace_types:
  - remote
  - hybrid
  - onsite

# Experience level mapping:
# 1: Internship | 2: Entry level | 3: Associate | 4: Mid-Senior
experience_level:
  - 1
  - 2
```

### 3. `questions_answers.yaml` (Answer Profile & Rules)
```yaml
version: 1

defaults:
  unknown_years: "0"
  unknown_text: "user provided"
  yes: "Yes"
  no: "No"

profile:
  years:
    python: "2"
    sql: "2"
    backend: "2"
    web_development: "2"
    cybersecurity: "2"
    machine_learning: "1"
  work_auth:
    require_sponsorship: "No"
    legally_authorized: "Yes"

rules:
  - id: python_experience
    match_any:
      - "(?i)years of python"
      - "(?i)experience with python"
    answer: "{years.python}"

  - id: sponsorship
    match_any:
      - "(?i)require sponsorship"
      - "(?i)need visa sponsorship"
    answer: "{require_sponsorship}"
```

### 4. `resumes/` Directory & Multi-Resume Uploads
Place your PDF resume files inside the `resumes/` directory. By default, `config.yaml` points to `resumes/resume.pdf`:

```yaml
uploads:
  Resume: "resumes/resume.pdf"
  # Target-specific resumes:
  # data: "resumes/data_engineer_resume.pdf"
  # python: "resumes/python_resume.pdf"
  # "Cover Letter": "resumes/cover_letter.pdf"
```

When an Easy Apply form requests an explicit resume file upload, the bot matches the job title against your configured upload keys and uploads the corresponding file. If a file is missing from disk, a clear warning is logged without crashing the session.

---

## CLI Flags & Options

The bot supports command-line flags to customize any session on the fly:

```bash
# Run in headless mode without opening Chrome UI
python easy_apply_bot.py --headless

# Test search and form-filling without submitting applications
python easy_apply_bot.py --dry-run

# Filter only jobs posted within the last 24 hours
python easy_apply_bot.py --date-posted past_24h

# Filter only Remote jobs
python easy_apply_bot.py --remote-only

# Limit the maximum applications for this session
python easy_apply_bot.py --max-apps 25
```

---

## Engineering Decisions & Presentation Highlights

If showcasing this project in technical reviews or interviews, highlight these core design decisions:

1. **Domain-Driven Design (DDD) & Layered Architecture**:
   - `domain/`: Pure dataclasses (`AppConfig`, `RunConfig`, `JobMetadata`).
   - `infra/`: Browser automation factory, Bezier trajectory generator, repositories.
   - `qa/`: `RelevanceScorer`, `AutoAnswer` pattern matching, and universal REST LLM client.
   - `services/`: Business logic, state machines, external ATS gate, and SDUI form handlers.
   - `dashboard/`: Flask control center and REST streaming.
2. **Anti-Fingerprinting & Behavioral Simulation**:
   - Uses `undetected-chromedriver` with overridden Chrome properties, single-click randomization, and cubic Bezier curves to emulate human cursor physics.
3. **Pre-Click Filtration Pipeline**:
   - Reduces wasted session time by evaluating search result cards before page loads, bypassing blacklisted or irrelevant positions immediately.
4. **Decoupled Page Object Model (`locators.yaml`)**:
   - HTML selectors are externalized into `locators.yaml`. UI updates on LinkedIn require **zero code changes**.
5. **Hybrid PII Protection**:
   - High-sensitivity data (credentials, phone, name, email) is isolated into `.env` and `resume.md` (gitignored), ensuring no personal data is committed to source control.
6. **Self-Learning QA Architecture**:
   - Combines deterministic regex rules with zero-shot LLM reasoning and auto-persisting cache for efficient, cost-free answer reuse.
7. **Atomic Persistence & Self-Healing Telemetry**:
   - Results and reports employ atomic temp-file replace operations (`.tmp` + `replace()`), eliminating truncation risk on abrupt user cancellation (Ctrl+C) and automatically recovering corrupted logs via timestamped backups.
8. **Resilient Multi-Selector Job Card Resolution**:
   - Avoids single-selector layout fragility by unifying CSS containers, occludable job IDs, entity URNs, and anchor regex extraction into a fault-tolerant discovery loop.

---

## Troubleshooting & FAQ

### 1. Chrome Version / Driver Mismatches
* **Symptom**: `SessionNotCreatedException` or Chrome driver startup error.
* **Resolution**: Ensure your installed Google Chrome browser is up to date (`chrome://settings/help`). The bot uses `undetected-chromedriver` which automatically retrieves the compatible driver binary. If issues persist, delete the cached chromedriver folder in your system temporary directory.

### 2. Daily Easy Apply Limit Reached
* **Symptom**: LinkedIn displays "You reached today's Easy Apply limit" or "We limit Easy Apply submissions to protect our community".
* **Resolution**: LinkedIn imposes dynamic rolling limits on Easy Apply submissions (often 50-100 per 24 hours depending on account age and verification status). When this happens, the bot's limit detector automatically stops the session cleanly and records the event in `logs/events.jsonl`. Wait until the following day for LinkedIn to reset your quota.

### 3. Login Checkpoints & Two-Factor Authentication
* **Symptom**: LinkedIn triggers SMS verification, email code, or CAPTCHA challenge upon login.
* **Resolution**: Run the bot in non-headless mode (without `--headless`). Complete the verification challenge directly in the opened Chrome browser window. Once logged in, the session service automatically saves authentication cookies to `.auth/linkedin_cookies.json`, enabling future sessions to authenticate without repeating verification.

### 4. Resume File Missing Warning
* **Symptom**: Warning logged: `Resume file configured at 'resumes/resume.pdf' does not exist on disk`.
* **Resolution**: Place your PDF resume in the `resumes/` folder (default name `resumes/resume.pdf`), or update the path under `uploads` in `config.yaml` to match your resume's location.

### 5. Graceful Shutdown & Cookie Preservation
* **Symptom**: Stopping the bot with Ctrl+C.
* **Resolution**: Pressing `Ctrl+C` once sends a graceful stop request, permitting the bot to finalize the active step and persist session cookies before quitting. Pressing `Ctrl+C` a second time forces an immediate exit.

---

## Testing & Quality Assurance

The codebase is tested with unit and mock-based tests:

```bash
# Run full pytest suite with coverage
python -m pytest tests/ -v --cov=easy_apply_automator --cov-report=term-missing

# Linting with Ruff
python -m ruff check .

# Static type checking with Mypy
python -m mypy easy_apply_automator
```

Continuous Integration (`.github/workflows/ci.yml`) runs tests, type checking, and linter validation on every push.

---

## License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
