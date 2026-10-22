# Video script - 8 to 10 minutes (talking points, record yourself)

> Record your own screen and voice. Run everything live before recording so the timings
> below are real. Replace bracketed notes with what actually happens on your machine.

## 1. Live Demo (3-4 min)

- 0:00-0:30 - Show the repo layout and `uvicorn app.main:app --reload` starting. Say:
  "One endpoint, POST /agent, takes any natural-language business request."
- 0:30-2:00 - **Standard request.** Send the wiki-migration request via curl or Swagger UI
  (/docs). Walk the JSON response: the agent's own TODO plan (analyze -> outline -> draft ->
  review -> export), then `GET /download/{id}` and open the .docx. Scroll: title block,
  assumptions list, six headed sections, footer.
- 2:00-3:30 - **Complex request.** Send the board/Q3 request. Point at the assumptions array:
  "The brief is ambiguous - unconfirmed budget, vague timing - so instead of asking questions
  the agent records assumptions and keeps going." Open the second .docx.
- Say once, on camera: which provider ran (shown as `provider` in the response) - e.g.
  "groq/llama-3.3-70b-versatile on the free tier" or, if no key: "the offline mock fallback,
  which exists so the demo can never die on a rate limit."

## 2. What You Built (2-3 min)

- Architecture (draw or show README): FastAPI -> Agent orchestrator -> Planner (LLM) ->
  section drafter (LLM) -> review check -> python-docx renderer.
- Planning logic: the planner prompt demands one JSON object (doc_type, title, assumptions,
  tasks, sections); `extract_json` tolerates code fences and prose; a schema check guards it.
- LLM integration: provider chain in `app/llm.py` - Groq, Gemini, Ollama, mock; one
  `LLMClient.complete()` for every call site.
- Tool usage: document generation is a deterministic tool (`app/docgen.py`) - the LLM plans
  and writes prose, code owns layout.
- API design: POST /agent (validated with pydantic, min request length), GET /download/{id},
  GET /health.

## 3. Debugging Insight (1-2 min)

Real issue hit while building this (test `test_dirty_json_recovery` encodes it):

- **Issue:** LLMs rarely return bare JSON. Replies come back wrapped in json code fences with
  prose around them, and a strict json.loads on the whole reply throws - the first version
  of the planner crashed on exactly this.
- **Root cause:** the parser assumed the whole reply was the payload. Chat models treat the
  JSON as content inside a conversational message.
- **Fix:** `extract_json` strips fences and uses `json.JSONDecoder().raw_decode` from the
  first `{`, then a schema check (`_valid`) rejects plausible-looking but wrong shapes; one
  strict retry, then a deterministic fallback plan. Show the test going green.

If you hit a different real issue while running it yourself (rate limit, timeout, Ollama
cold start), use that one instead - a true story beats this one.

## 4. Tradeoff Discussion (1-2 min)

**Autonomous planning vs deterministic workflows** - this build is deliberately a hybrid:

- The LLM chooses the plan (doc type, tasks, sections) - flexible across proposals, SOPs,
  reports, minutes, without per-type code.
- Execution is deterministic: tasks run in order, the review bar is a rule, the .docx layout
  is code, and an invalid plan falls back to a fixed structure.
- Cost of the choice: the plan can be generic on vague requests (mitigated by recorded
  assumptions) and the fixed executor can't reorder tasks. Win: the demo is repeatable -
  the LLM can surprise you with content, never with a crash.
