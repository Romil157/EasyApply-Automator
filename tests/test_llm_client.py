"""Unit tests for universal LLMClient and AI Auto-Answer integration."""

from __future__ import annotations

import io
import json
import os
from unittest.mock import MagicMock, patch

from easy_apply_automator.qa.auto_answer import AutoAnswer
from easy_apply_automator.qa.llm_client import LLMClient


class TestLLMClientInitialization:
    @patch.dict(os.environ, {}, clear=True)
    def test_auto_provider_selection_gemini(self):
        client = LLMClient(provider="auto", gemini_api_key="AIzaSyDummyKey")
        assert client.provider == "gemini"
        assert client.model == "gemini-1.5-flash"
        assert client.is_available() is True

    @patch.dict(os.environ, {}, clear=True)
    def test_auto_provider_selection_groq(self):
        client = LLMClient(provider="auto", groq_api_key="gsk_DummyKey")
        assert client.provider == "groq"
        assert client.model == "openai/gpt-oss-120b"
        assert client.is_available() is True

    @patch.dict(os.environ, {}, clear=True)
    def test_auto_provider_selection_openai(self):
        client = LLMClient(provider="auto", openai_api_key="sk-dummykey")
        assert client.provider == "openai"
        assert client.model == "gpt-4o-mini"
        assert client.is_available() is True

    @patch.dict(os.environ, {}, clear=True)
    def test_provider_none_when_no_keys(self):
        client = LLMClient(
            provider="auto",
            gemini_api_key="",
            openai_api_key="",
            groq_api_key="",
            anthropic_api_key="",
            ollama_host="",
        )
        assert client.is_available() is False

    def test_clean_response_strips_markdown_and_quotes(self):
        assert LLMClient._clean_response('```json\n"2"\n```') == "2"
        assert LLMClient._clean_response('"Yes"') == "Yes"
        assert LLMClient._clean_response("  Yes  ") == "Yes"


class TestBuildPrompt:
    def test_build_prompt_includes_context_and_question(self):
        client = LLMClient(provider="gemini", gemini_api_key="AIzaSyDummyKey")
        profile_context = {
            "skill_experience_years": {"python": "2", "sql": "2"},
            "candidate_name": "Test User",
        }
        prompt = client.build_prompt("How many years of Python experience do you have?", profile_context)
        assert "How many years of Python experience do you have?" in prompt
        assert "Test User" in prompt
        assert '"python": "2"' in prompt


class TestLLMAPICalls:
    @patch("urllib.request.urlopen")
    def test_call_gemini_success(self, mock_urlopen):
        client = LLMClient(provider="gemini", gemini_api_key="AIzaSyDummyKey")
        gemini_response_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "2"}]
                    }
                }
            ]
        }
        mock_resp = io.BytesIO(json.dumps(gemini_response_data).encode("utf-8"))
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        ans = client.answer_question("How many years of Python experience?", {"skill_experience_years": {"python": "2"}})
        assert ans == "2"

    @patch("urllib.request.urlopen")
    def test_call_openai_success(self, mock_urlopen):
        client = LLMClient(provider="openai", openai_api_key="sk-dummykey")
        openai_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "Yes"
                    }
                }
            ]
        }
        mock_resp = io.BytesIO(json.dumps(openai_response_data).encode("utf-8"))
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        ans = client.answer_question("Are you willing to relocate?", {})
        assert ans == "Yes"

    @patch("urllib.request.urlopen")
    def test_call_ollama_success(self, mock_urlopen):
        client = LLMClient(provider="ollama", ollama_host="http://localhost:11434")
        ollama_response_data = {
            "response": "Bachelor's Degree in Computer Engineering"
        }
        mock_resp = io.BytesIO(json.dumps(ollama_response_data).encode("utf-8"))
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        ans = client.answer_question("What is your highest degree?", {})
        assert ans == "Bachelor's Degree in Computer Engineering"


class TestAutoAnswerAIIntegration:
    def test_auto_answer_falls_back_to_llm_when_rules_do_not_match(self, tmp_path):
        ans_yaml = tmp_path / "questions_answers.yaml"
        ans_yaml.write_text("version: 1\ndefaults:\n  unknown_text: 'user provided'\nrules: []\n", encoding="utf-8")

        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.auto_learn = True
        mock_llm.answer_question.return_value = "3 years of distributed systems experience"

        auto_ans = AutoAnswer(
            qa_file=None,
            ans_yaml_path=ans_yaml,
            salary="100000",
            hourly_rate="50",
            answers={},
            log=MagicMock(),
            llm_client=mock_llm,
        )

        ans = auto_ans.ans_question("Describe your experience with async message brokers like Kafka.")
        assert ans == "3 years of distributed systems experience"
        mock_llm.answer_question.assert_called_once()

        # Check that the answer was auto-persisted to the YAML file
        yaml_content = ans_yaml.read_text(encoding="utf-8")
        assert "ai_" in yaml_content
        assert "3 years of distributed systems experience" in yaml_content
