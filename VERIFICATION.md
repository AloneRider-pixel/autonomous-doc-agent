# Requirement checklist - what was actually run (Oct 22, 2026)

| # | Brief requirement | Status | Evidence |
|---|---|---|---|
| 1 | Python API, FastAPI preferred, POST /agent accepting {"request":"..."} | VERIFIED | Live uvicorn server: POST /agent returned 200 with plan+steps; GET /download returned the .docx (38 KB, valid zip). TestClient test `test_api_roundtrip` also passes. |
| 2 | Accept natural-language request, determine tasks, generate own execution plan | VERIFIED | Every run logs "plan ready: 5 tasks, 6 sections" with the agent-generated JSON plan (see `python demo.py` output). |
| 3 | Execute each step and return meaningful response + generated Word doc | VERIFIED | Response includes timestamped step trace; .docx files produced for all runs; sample outputs in outputs/. |
| 4 | Document may be proposal/minutes/plan/report/SOP/spec etc. | VERIFIED | doc_type detection exercised: project_plan (standard input), report (complex input), sop (live server run). |
| 5 | Free/local LLM (Groq/Gemini/Ollama/other) | PARTIAL | Provider chain implemented for Groq, Gemini, Ollama; no API key was available in the build environment, so end-to-end verification used the documented offline mock fallback. Live LLM path needs one free key at demo time. |
| 6 | ONE real engineering improvement, explained | VERIFIED | Retry & fallback logic (LLMClient retries + backoff + provider fallback; planner invalid-JSON retry + fallback plan). Explained in README; proven by tests `test_dirty_json_recovery` and `test_invalid_plan_fallback`. |
| 7 | Two test inputs: one standard, one complex/ambiguous | VERIFIED | Both defined in demo.py and tests; both run for real; the complex input yields recorded assumptions (no stalling) and a complete document. |
| 8 | Tests pass | VERIFIED | `pytest tests -q` -> 6 passed. |
| 9 | README | VERIFIED | README.md (this repo). |
| 10 | Video: live demo 3-4 min, what-you-built 2-3 min, debugging 1-2 min, tradeoff 1-2 min | PREPARED | VIDEO_SCRIPT.md with per-section timings and talking points. The recording itself must be done by the applicant. |
