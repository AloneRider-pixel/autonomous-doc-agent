"""LLM access with retry + fallback across providers.

Provider chain (first available wins; on failure the next provider takes over):
  1. Groq    - needs GROQ_API_KEY    (free tier: https://console.groq.com)
  2. Gemini  - needs GEMINI_API_KEY  (free tier: https://aistudio.google.com)
  3. Ollama  - needs a local server  (ollama pull llama3.2)
  4. Mock    - deterministic offline fallback, always available.

Set AGENT_LLM=mock to force the offline provider (used by the test-suite).
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.request


class LLMError(RuntimeError):
    pass


def _post_json(url, payload, headers=None, timeout=60):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


class Provider:
    name = "base"

    def available(self) -> bool:
        return False

    def complete(self, prompt: str) -> str:
        raise NotImplementedError


class GroqProvider(Provider):
    def __init__(self, model="llama-3.3-70b-versatile"):
        self.key = os.getenv("GROQ_API_KEY")
        self.model = model
        self.name = f"groq/{model}"

    def available(self):
        return bool(self.key)

    def complete(self, prompt):
        data = _post_json(
            "https://api.groq.com/openai/v1/chat/completions",
            {"model": self.model,
             "messages": [{"role": "user", "content": prompt}],
             "temperature": 0.4},
            headers={"Authorization": f"Bearer {self.key}"}, timeout=30)
        return data["choices"][0]["message"]["content"]


class GeminiProvider(Provider):
    def __init__(self, model="gemini-2.0-flash"):
        self.key = os.getenv("GEMINI_API_KEY")
        self.model = model
        self.name = f"gemini/{model}"

    def available(self):
        return bool(self.key)

    def complete(self, prompt):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.key}")
        data = _post_json(url, {"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        return data["candidates"][0]["content"]["parts"][0]["text"]


class OllamaProvider(Provider):
    def __init__(self, model=None, base="http://localhost:11434"):
        self.base = base.rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
        self.name = f"ollama/{self.model}"

    def available(self):
        try:
            with urllib.request.urlopen(self.base + "/api/tags", timeout=2):
                return True
        except Exception:
            return False

    def complete(self, prompt):
        data = _post_json(self.base + "/api/generate",
                          {"model": self.model, "prompt": prompt, "stream": False},
                          timeout=120)
        return data["response"]


class MockProvider(Provider):
    """Deterministic offline stand-in so the whole pipeline runs with no API key.

    It recognises the planner (PLAN_JSON:) and section-writer (SECTION:)
    prompt markers and returns request-aware structured content. Clearly not a
    real LLM: swap in Groq/Gemini/Ollama for the graded run.
    `dirty=True` wraps the plan in prose + code fences to exercise the parser's
    recovery path (see tests).
    """

    name = "mock/offline-deterministic"

    def __init__(self, dirty=False):
        self.dirty = dirty

    def available(self):
        return True

    def complete(self, prompt):
        if prompt.startswith("PLAN_JSON:"):
            return self._plan(prompt)
        if prompt.startswith("SECTION:"):
            return self._section(prompt)
        return "Mock LLM response (no API key configured)."

    def _plan(self, prompt):
        request = prompt.split("USER REQUEST:", 1)[-1].strip()
        low = request.lower()
        doc_type = "report"
        for key, dt in [("proposal", "proposal"), ("sop", "sop"),
                        ("standard operating", "sop"), ("minutes", "meeting_minutes"),
                        ("spec", "product_spec"), ("design", "technical_design"),
                        ("plan", "project_plan"), ("report", "business_report")]:
            if key in low:
                doc_type = dt
                break
        words = request.split()
        title = " ".join(words[:8]).rstrip(".,;:") or "Generated Document"
        title = title[0].upper() + title[1:]
        assumptions = self._assumptions(request)
        plan = {
            "doc_type": doc_type,
            "title": title,
            "assumptions": assumptions,
            "tasks": [
                {"id": 1, "title": "Analyze request and resolve gaps", "kind": "analyze",
                 "detail": "Identify document type, audience, and missing facts; record assumptions."},
                {"id": 2, "title": "Outline document", "kind": "outline",
                 "detail": "Fix section list and the goal of each section."},
                {"id": 3, "title": "Draft all sections", "kind": "draft",
                 "detail": "Write the body of every planned section."},
                {"id": 4, "title": "Review draft", "kind": "review",
                 "detail": "Check every section meets the minimum substance bar; expand thin ones."},
                {"id": 5, "title": "Export Word document", "kind": "export",
                 "detail": "Render the polished .docx deliverable."},
            ],
            "sections": [
                {"heading": "Executive Summary", "goal": "One-paragraph overview of the request, the decision taken, and the outcome."},
                {"heading": "Background and Objectives", "goal": "Context behind the request and what success looks like."},
                {"heading": "Scope and Assumptions", "goal": "What is in/out of scope and every assumption made."},
                {"heading": "Approach and Plan", "goal": "Step-by-step approach with owners and milestones (mock data where needed)."},
                {"heading": "Risks and Mitigations", "goal": "Top risks with a mitigation for each."},
                {"heading": "Next Steps", "goal": "Concrete, dated follow-up actions."},
            ],
        }
        out = json.dumps(plan, indent=2)
        if self.dirty:
            return "Here is the plan you asked for:\n```json\n" + out + "\n```\nLet me know if you want changes."
        return out

    def _assumptions(self, request):
        low = request.lower()
        out = []
        if any(w in low for w in ["might", "maybe", "not confirmed", "tbd", "unclear", "something"]):
            out.append("The request contains open or ambiguous points; reasonable defaults were chosen and recorded here.")
        if "board" in low:
            out.append("Audience assumed to be the board of directors: concise, decision-oriented language used.")
        out.append("Audience, dates, and figures not supplied in the request are realistic mock values.")
        return out

    def _section(self, prompt):
        heading = prompt.split('"')[1] if '"' in prompt else "Section"
        req_line = [l for l in prompt.splitlines() if l.startswith("Original user request:")]
        req = req_line[0].split(":", 1)[-1].strip() if req_line else "the user's request"
        short = " ".join(req.split()[:14])
        return (
            f"{heading}: this section addresses \"{short}\". The content below is generated "
            f"offline as deterministic mock output so the full pipeline can be exercised without "
            f"an API key; with Groq, Gemini, or Ollama configured, the same prompt produces "
            f"fully written prose.\n"
            f"Key points are organised around the stated goal of this section. Mock specifics "
            f"(owner: Priya S., target date: 2026-11-15, budget placeholder: Rs 4.5L) are used "
            f"where the original request left gaps, and each placeholder is listed under "
            f"Assumptions so a reviewer can correct it.\n"
            f"In a production run this block would be several focused paragraphs tailored to the "
            f"request, the chosen document type, and the section goal."
        )


class LLMClient:
    """One entry point. Tries the active provider with retries + jittered
    backoff, then falls back down the provider chain. Every failure is
    recorded in self.attempts for observability."""

    def __init__(self, providers=None, retries=2):
        if providers is None and os.getenv("AGENT_LLM") == "mock":
            providers = [MockProvider()]
        self.providers = providers or [GroqProvider(), GeminiProvider(), OllamaProvider(), MockProvider()]
        self.retries = retries
        self.attempts = []
        self.active = next((p for p in self.providers if p.available()), MockProvider())

    def complete(self, prompt: str) -> str:
        last_err = None
        chain = [self.active] + [p for p in self.providers if p is not self.active]
        for provider in chain:
            if not provider.available():
                self.attempts.append((provider.name, "unavailable"))
                continue
            for i in range(self.retries):
                try:
                    out = provider.complete(prompt)
                    self.active = provider
                    self.attempts.append((provider.name, "ok"))
                    return out
                except Exception as exc:  # noqa: BLE001 - any provider error triggers retry/fallback
                    last_err = exc
                    self.attempts.append((provider.name, f"error: {exc}"))
                    time.sleep(min(2 ** i, 4) * 0.5 + random.uniform(0, 0.3))
        raise LLMError(f"all providers failed; last error: {last_err}")
