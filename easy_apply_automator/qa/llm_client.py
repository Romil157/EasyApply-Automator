"""Universal AI / LLM client for zero-shot job application question answering.

Supports Google Gemini, OpenAI / OpenAI-compatible (Ollama / Groq / OpenRouter),
Anthropic Claude, and local Ollama REST endpoints without requiring heavy SDK dependencies.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


class LLMClient:
    """Zero-shot question answering engine backed by Groq, Gemini, OpenAI, Claude, or local Ollama."""

    def __init__(
        self,
        provider: str = "auto",
        gemini_api_key: str = "",
        openai_api_key: str = "",
        openai_base_url: str = "",
        groq_api_key: str = "",
        anthropic_api_key: str = "",
        ollama_host: str = "",
        model: str = "",
        auto_learn: bool = True,
        log: Any = None,
    ):
        self.log = log
        self.gemini_api_key = (
            gemini_api_key.strip() if gemini_api_key else os.getenv("GEMINI_API_KEY", "").strip()
        )
        self.groq_api_key = (
            groq_api_key.strip() if groq_api_key else os.getenv("GROQ_API_KEY", "").strip()
        )
        self.openai_api_key = (
            openai_api_key.strip()
            if openai_api_key
            else (self.groq_api_key or os.getenv("OPENAI_API_KEY", "").strip())
        )

        default_base_url = (
            "https://api.groq.com/openai/v1"
            if self.groq_api_key or provider.lower() == "groq"
            else "https://api.openai.com/v1"
        )
        self.openai_base_url = (
            openai_base_url
            if openai_base_url
            else os.getenv("OPENAI_BASE_URL", default_base_url).strip().rstrip("/")
        )
        self.anthropic_api_key = (
            anthropic_api_key.strip()
            if anthropic_api_key
            else os.getenv("ANTHROPIC_API_KEY", "").strip()
        )
        self.ollama_host = (
            ollama_host.strip()
            if ollama_host
            else os.getenv("OLLAMA_HOST", "http://localhost:11434").strip().rstrip("/")
        )
        self.auto_learn = auto_learn

        # Determine effective provider
        p = (provider or os.getenv("AI_PROVIDER", "auto")).strip().lower()
        if p == "auto":
            if groq_api_key:
                p = "groq"
            elif gemini_api_key:
                p = "gemini"
            elif openai_api_key:
                p = "openai"
            elif anthropic_api_key:
                p = "anthropic"
            elif self.groq_api_key:
                p = "groq"
            elif self.gemini_api_key:
                p = "gemini"
            elif self.openai_api_key:
                p = "openai"
            elif self.anthropic_api_key:
                p = "anthropic"
            elif self.ollama_host and os.getenv("USE_OLLAMA", "").lower() in ("1", "true", "yes"):
                p = "ollama"
            else:
                p = "none"
        self.provider = p

        # Default model per provider
        default_models = {
            "groq": "openai/gpt-oss-120b",
            "gemini": "gemini-1.5-flash",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-haiku-20241022",
            "ollama": "llama3.2",
        }
        self.model = (model or os.getenv("AI_MODEL", "")).strip() or default_models.get(
            self.provider, ""
        )

    @classmethod
    def from_env_or_config(cls, cfg: dict | None = None, log: Any = None) -> LLMClient:
        cfg = cfg or {}
        ai_cfg = cfg.get("ai", {}) if isinstance(cfg, dict) else {}
        return cls(
            provider=ai_cfg.get("provider", ""),
            gemini_api_key=ai_cfg.get("gemini_api_key", ""),
            groq_api_key=ai_cfg.get("groq_api_key", ""),
            openai_api_key=ai_cfg.get("openai_api_key", ""),
            openai_base_url=ai_cfg.get("openai_base_url", ""),
            anthropic_api_key=ai_cfg.get("anthropic_api_key", ""),
            ollama_host=ai_cfg.get("ollama_host", ""),
            model=ai_cfg.get("model", ""),
            auto_learn=bool(ai_cfg.get("auto_learn", True)),
            log=log,
        )

    def is_available(self) -> bool:
        if self.provider == "groq":
            return bool(self.groq_api_key or self.openai_api_key)
        if self.provider == "gemini":
            return bool(self.gemini_api_key)
        if self.provider == "openai":
            return bool(self.openai_api_key)
        if self.provider == "anthropic":
            return bool(self.anthropic_api_key)
        if self.provider == "ollama":
            return bool(self.ollama_host)
        return False

    def build_prompt(self, question: str, profile_context: dict[str, Any]) -> str:
        profile_json = json.dumps(profile_context, indent=2, ensure_ascii=False)
        job_target = ""
        if profile_context.get("current_job_title"):
            job_target = f"\nTarget Position: {profile_context['current_job_title']}"
            if profile_context.get("current_job_company"):
                job_target += f" at {profile_context['current_job_company']}"
            job_target += "\nTailor open-ended answers directly to this role and company when relevant.\n"

        return (
            "You are an expert AI job application assistant answering a single question on a job application form on behalf of the candidate.\n\n"
            f"Candidate Profile & Data:\n{profile_json}\n"
            f"{job_target}\n"
            f"Question on Job Form:\n\"{question}\"\n\n"
            "Rules for answering:\n"
            "1. If the question asks for years of experience or a numeric quantity (e.g. 'How many years of Python experience?'), respond with ONLY the integer or decimal number (e.g. '2' or '0'). Do not write extra words or units.\n"
            "2. If the question is a Yes/No or confirmation question, answer ONLY 'Yes' or 'No'.\n"
            "3. If the question is a short free-form essay or prompt (e.g. 'Why are you interested in this role?' or 'Describe a project'), provide a concise, high-impact, professional 1-2 sentence answer tailored to the candidate's background.\n"
            "4. Never hallucinate facts outside the candidate profile. If experience with a skill is not listed, assume 0 or 1 year consistent with candidate profile.\n"
            "5. Return ONLY the direct answer text. Do NOT include quotes, preamble, greetings, or markdown code fences."
        )

    def answer_question(
        self, question: str, profile_context: dict[str, Any], timeout_seconds: float = 8.0
    ) -> str | None:
        if not self.is_available() or not question:
            return None

        prompt = self.build_prompt(question, profile_context)
        try:
            if self.provider in ("openai", "groq"):
                return self._call_openai(prompt, timeout_seconds)
            if self.provider == "gemini":
                return self._call_gemini(prompt, timeout_seconds)
            if self.provider == "anthropic":
                return self._call_anthropic(prompt, timeout_seconds)
            if self.provider == "ollama":
                return self._call_ollama(prompt, timeout_seconds)
        except Exception as exc:
            if self.log:
                self.log.debug(f"LLM API query failed ({self.provider}): {exc}")
            return None
        return None

    def _call_gemini(self, prompt: str, timeout_seconds: float) -> str | None:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.gemini_api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1000,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            candidates = body.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return self._clean_response(parts[0].get("text", ""))
        return None

    def _call_openai(self, prompt: str, timeout_seconds: float) -> str | None:
        url = f"{self.openai_base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional job application assistant. Output only the direct answer to the form question.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices", [])
            if choices:
                msg = choices[0].get("message", {}).get("content", "")
                return self._clean_response(msg)
        return None

    def _call_anthropic(self, prompt: str, timeout_seconds: float) -> str | None:
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": self.model,
            "max_tokens": 1000,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content = body.get("content", [])
            if content and isinstance(content, list):
                return self._clean_response(content[0].get("text", ""))
        return None

    def _call_ollama(self, prompt: str, timeout_seconds: float) -> str | None:
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1000},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return self._clean_response(body.get("response", ""))
        return None

    @staticmethod
    def _clean_response(text: str) -> str:
        cleaned = (text or "").strip()
        # Normalize Unicode spaces, hyphens, and quotes
        cleaned = (
            cleaned.replace("\u202f", " ")
            .replace("\xa0", " ")
            .replace("\u200b", "")
            .replace("’", "'")
            .replace("‘", "'")
            .replace("“", '"')
            .replace("”", '"')
            .replace("—", "-")
            .replace("–", "-")
            .replace("\u2011", "-")
            .replace("\u2010", "-")
        )
        cleaned = re.sub(r"^```(?:json|text)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = re.sub(r"^[\"']|[\"']$", "", cleaned).strip()
        return cleaned
