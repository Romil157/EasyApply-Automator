from __future__ import annotations

import urllib.parse
from unittest.mock import MagicMock

from easy_apply_automator.app.search_loop import SearchLoopMixin


class DummySearchBot(SearchLoopMixin):
    def __init__(self):
        self.experience_level = [2, 3]
        self.date_posted = "past_week"
        self.workplace_types = ["remote", "hybrid"]
        self.job_types = ["full_time", "contract"]
        self.max_applications = 10
        self.session_jobs_submitted = 0
        self.stop_requested = False
        self.session_deadline = 9999999999.0
        self.appliedJobIDs = []


class TestBuildSearchUrl:
    def test_build_search_url_with_all_filters(self):
        bot = DummySearchBot()
        url = bot.build_search_url("Software Engineer", "&location=United States", 0)

        assert "https://www.linkedin.com/jobs/search/?" in url
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)

        assert qs["keywords"] == ["Software Engineer"]
        assert qs["location"] == ["United States"]
        assert qs["f_LF"] == ["f_AL"]
        assert qs["f_E"] == ["2,3"]
        assert qs["f_TPR"] == ["r604800"]
        assert qs["f_WT"] == ["2,3"]
        assert qs["f_JT"] == ["F,C"]
        assert qs["start"] == ["0"]

    def test_build_search_url_past_24h(self):
        bot = DummySearchBot()
        bot.date_posted = "past_24h"
        bot.workplace_types = ["remote"]
        bot.job_types = ["full_time"]
        url = bot.build_search_url("Python Developer", "", 25, experience_level=[1])

        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)

        assert qs["f_TPR"] == ["r86400"]
        assert qs["f_WT"] == ["2"]
        assert qs["f_JT"] == ["F"]
        assert qs["f_E"] == ["1"]
        assert qs["start"] == ["25"]


class TestMatchesSelectedExperienceLevel:
    def test_matches_internship_via_title(self):
        bot = DummySearchBot()
        bot.experience_level = [1]
        bot.browser = MagicMock()
        bot.browser.title = "Software Engineer Intern | Company | LinkedIn"
        bot.browser.find_elements.return_value = []

        assert bot._matches_selected_experience_level() is True

    def test_matches_internship_via_sdui_badge(self):
        bot = DummySearchBot()
        bot.experience_level = [1]
        bot.browser = MagicMock()
        bot.browser.title = "ERP Specialist | Company | LinkedIn"

        badge_mock = MagicMock()
        badge_mock.is_displayed.return_value = True
        badge_mock.text = "Internship"

        bot.browser.find_elements.return_value = [badge_mock]

        assert bot._matches_selected_experience_level() is True

    def test_rejects_non_internship_when_level_is_1(self):
        bot = DummySearchBot()
        bot.experience_level = [1]
        bot.browser = MagicMock()
        bot.browser.title = "Senior Architect | Company | LinkedIn"
        bot.browser.find_elements.return_value = []

        assert bot._matches_selected_experience_level() is False

