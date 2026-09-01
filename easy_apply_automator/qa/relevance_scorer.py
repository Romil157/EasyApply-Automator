"""Job title relevance scoring against candidate resume profile.

Evaluates job posting titles against technical skills, domain expertise,
and career aspirations extracted from candidate resume data. Identifies
irrelevant roles and hard blockers before attempting form submission.
"""

from __future__ import annotations

import re


class RelevanceScorer:
    """Evaluates whether a job title is relevant to the candidate resume."""

    # Keywords extracted from candidate resume profile
    RESUME_KEYWORDS: set[str] = {
        # Programming & Frameworks
        "python",
        "sql",
        "javascript",
        "js",
        "node",
        "nodejs",
        "node.js",
        "flask",
        "html",
        "css",
        "programming",
        "coding",
        # Data Engineering & Analytics
        "data",
        "scraping",
        "scraper",
        "crawler",
        "etl",
        "pipeline",
        "pipelines",
        "cleaning",
        "analytics",
        "analyst",
        "excel",
        "bi",
        "business intelligence",
        "research",
        "dataset",
        "datasets",
        # AI / ML / NLP
        "ai",
        "ml",
        "machine learning",
        "nlp",
        "rag",
        "llm",
        "llms",
        "generative",
        "artificial intelligence",
        "deep learning",
        # Cybersecurity & Information Security
        "security",
        "cybersecurity",
        "cyber security",
        "siem",
        "phishing",
        "soc",
        "infosec",
        "threat",
        "vulnerability",
        "information security",
        # IT Support & Infrastructure
        "it",
        "technical support",
        "tech support",
        "helpdesk",
        "help desk",
        "network",
        "networks",
        "networking",
        "sysadmin",
        "system administrator",
        "desktop support",
        "it support",
        "it intern",
        "it analyst",
        # Web & Software Development
        "software",
        "developer",
        "engineer",
        "engineering",
        "web",
        "backend",
        "back-end",
        "frontend",
        "front-end",
        "full stack",
        "fullstack",
        "full-stack",
        "api",
        "apis",
        "saas",
        "application",
        "applications",
        "chrome extension",
        "browser extension",
        "automation",
        "qa",
        "testing",
        "test",
        "quality assurance",
        "devops",
        "git",
        "deployment",
        # Finance & Growth (User requested)
        "finance",
        "financial",
        "investment",
        "banking",
        "fintech",
        "quantitative",
        "quant",
        "seo",
        "sem",
        "growth",
    }

    # Hard blocker phrases: roles completely irrelevant to a computer engineering / tech profile
    HARD_BLOCKERS: set[str] = {
        # Non-English language specific content creation / translation
        "kannada",
        "hindi",
        "tamil",
        "telugu",
        "malayalam",
        "bengali",
        "marathi",
        "urdu",
        "gujarati",
        "punjabi",
        "french speaker",
        "german speaker",
        "spanish speaker",
        "mandarin",
        "cantonese",
        "japanese speaker",
        "arabic speaker",
        # Media / Creative / Performing Arts
        "video creator",
        "video editor",
        "video editing",
        "video production",
        "video maker",
        "video producer",
        "photographer",
        "videographer",
        "cinematographer",
        "vlogger",
        "tiktok",
        "instagram reels",
        "reels creator",
        "youtube creator",
        "podcast",
        "audio engineer",
        "sound designer",
        "voice over",
        "actor",
        "actress",
        "model",
        "fashion",
        "stylist",
        "makeup",
        # Healthcare & Medical
        "nurse",
        "nursing",
        "physician",
        "doctor",
        "dentist",
        "dental",
        "therapist",
        "therapy",
        "physiotherapy",
        "pharmacy",
        "pharmacist",
        "clinical trial",
        "veterinarian",
        "radiology",
        "surgery",
        "surgical",
        # Education & Childcare
        "teacher",
        "tutor",
        "faculty",
        "professor",
        "lecturer",
        "kindergarten",
        "babysitter",
        "nanny",
        # Trades, Hospitality & Manual Labor
        "driver",
        "delivery",
        "warehouse",
        "kitchen",
        "cook",
        "chef",
        "carpenter",
        "plumber",
        "electrician",
        "mechanic",
        "welder",
        "construction",
        "mason",
        "painter",
        "housekeeper",
        "cleaner",
        "janitor",
        "barista",
        "waiter",
        "waitress",
        "bartender",
        # Real Estate & Insurance Sales
        "real estate agent",
        "realtor",
        "insurance agent",
        "loan officer",
        "mortgage broker",
    }

    def score(self, job_title: str) -> float:
        """Calculate a relevance score between 0.0 and 1.0 for the given job title."""
        if not job_title or not isinstance(job_title, str):
            return 0.0

        title_lower = job_title.lower().strip()
        if not title_lower:
            return 0.0

        # Check hard blockers first
        for blocker in self.HARD_BLOCKERS:
            if blocker in title_lower:
                return 0.0

        # Tokenize and match keywords
        # Split by non-alphanumeric (excluding dots for node.js / react.js)
        raw_tokens = re.split(r"[\s/\-_,&|()]+", title_lower)
        tokens = {t.strip() for t in raw_tokens if len(t.strip()) > 1}

        # Build bigrams for composite phrases (e.g., "data analyst", "full stack")
        token_list = [t for t in raw_tokens if t.strip()]
        bigrams = {
            f"{token_list[i]} {token_list[i+1]}"
            for i in range(len(token_list) - 1)
        }
        all_candidate_terms = tokens | bigrams

        matches = 0
        for kw in self.RESUME_KEYWORDS:
            if kw in all_candidate_terms or kw in title_lower:
                matches += 1

        if matches == 0:
            return 0.0

        # 1 match gives 0.5, 2+ matches give 1.0
        return min(1.0, matches * 0.5)

    def is_relevant(self, job_title: str, threshold: float = 0.15) -> bool:
        """Check if job title meets minimum relevance threshold."""
        return self.score(job_title) >= threshold
