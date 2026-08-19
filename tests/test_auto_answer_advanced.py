from __future__ import annotations

import logging

from easy_apply_automator.qa.auto_answer import AutoAnswer


def _make_auto_answer(
    profile_years: dict | None = None, work_auth: dict | None = None
) -> AutoAnswer:
    cfg = {
        "defaults": {
            "unknown_years": "0",
            "unknown_text": "user provided",
            True: "Yes",
            False: "No",
        },
        "profile": {
            "years": profile_years
            or {
                "python": "4",
                "sql": "3",
                "aws": "2",
                "machine_learning": "3",
                "react": "2",
                "overall_software": "5",
            },
            "work_auth": work_auth
            or {
                "legally_authorized": "Yes",
                "require_sponsorship": "No",
            },
            "demographics": {},
        },
        "rules": [
            {
                "id": "salary",
                "match_any": ["(?i)salary"],
                "answer": "{salary}",
            }
        ],
    }
    aa = AutoAnswer.__new__(AutoAnswer)
    aa.cfg = cfg
    aa.salary = "100000"
    aa.hourly_rate = "80"
    aa.answers = {}
    aa.log = logging.getLogger("test_qa")
    aa.qa_file = None
    aa.linkedin_profile_url = ""
    aa.full_name = "Jane Doe"
    aa.first_name = "Jane"
    aa.last_name = "Doe"
    aa.form_email = "jane@example.com"
    aa.phone_number = "1234567890"
    aa.github_url = "https://github.com/jane"
    aa.location_city = "New York"
    return aa


class TestDynamicSkillExtraction:
    def test_extract_years_exact_match(self):
        aa = _make_auto_answer()
        assert aa.ans_question("How many years of work experience do you have with Python?") == "4"
        assert aa.ans_question("How many years of experience do you have in SQL?") == "3"

    def test_extract_years_alias_match(self):
        aa = _make_auto_answer()
        assert aa.ans_question("How many years of experience do you have with React.js?") == "2"
        assert aa.ans_question("Years of experience with Amazon Web Services?") == "2"
        assert aa.ans_question("Years of experience in ML?") == "3"

    def test_normalize_skill_key(self):
        aa = _make_auto_answer()
        assert aa._normalize_skill_key("React.js") == "react"
        assert aa._normalize_skill_key("Node.js") == "nodejs"
        assert aa._normalize_skill_key("C++") == "cpp"
        assert aa._normalize_skill_key("Golang") == "go"
        assert aa._normalize_skill_key("Generative AI") == "llm_genai"


class TestHeuristicFallback:
    def test_notice_period_heuristic(self):
        aa = _make_auto_answer()
        assert aa.ans_question("What is your notice period?") == "Immediately"
        assert aa.ans_question("How soon can you start working?") == "Immediately"

    def test_relocation_and_commute_heuristic(self):
        aa = _make_auto_answer()
        assert aa.ans_question("Are you willing to relocate for this position?") == "Yes"
        assert aa.ans_question("Are you willing to commute daily to our office?") == "Yes"

    def test_driver_license_and_background(self):
        aa = _make_auto_answer()
        assert aa.ans_question("Do you possess a valid driver's license?") == "Yes"
        assert aa.ans_question("Are you willing to undergo a standard background check?") == "Yes"

    def test_degree_and_gpa(self):
        aa = _make_auto_answer()
        assert (
            aa.ans_question("What is your highest level of education completed?")
            == "Bachelor's Degree"
        )
        assert aa.ans_question("What was your undergraduate GPA / CGPA?") == "9.0"

    def test_work_authorization_fallback(self):
        aa = _make_auto_answer(work_auth={"legally_authorized": "Yes", "require_sponsorship": "No"})
        assert aa.ans_question("Are you legally authorized to work in this country?") == "Yes"
        assert aa.ans_question("Will you now or in the future require visa sponsorship?") == "No"
