"""Planning module: turns a natural-language request into a validated JSON plan.

The LLM is asked for ONE JSON object. Replies are parsed tolerantly (code
fences and surrounding prose are stripped) and schema-checked; an invalid
reply is retried once with a stricter instruction, and if it still fails a
deterministic fallback plan is used so the pipeline never dead-ends.
"""
import json
import re

PLAN_PROMPT = """PLAN_JSON:
You are the planning module of an autonomous business-document agent.
Read the user request and output ONE JSON object (no prose, no markdown) with exactly these keys:
{{
  "doc_type": one of ["proposal","project_plan","report","sop","meeting_minutes","product_spec","business_report","technical_design"],
  "title": "short document title",
  "assumptions": ["every gap or ambiguity you resolved yourself"],
  "tasks": [{{"id": 1, "title": "...", "kind": "analyze|outline|draft|review|export", "detail": "..."}}],
  "sections": [{{"heading": "...", "goal": "one line on what this section must cover"}}]
}}
Rules: 3-8 sections; tasks must be executable in order and end with an export task.
Never ask the user questions: record an assumption instead.
USER REQUEST: {request}
"""


def extract_json(text):
    """Pull the first JSON object out of an LLM reply (tolerates fences/prose)."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text)
    start = cleaned.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _valid(plan):
    return (
        isinstance(plan.get("title"), str)
        and isinstance(plan.get("sections"), list)
        and len(plan["sections"]) >= 2
        and all(isinstance(s, dict) and s.get("heading") for s in plan["sections"])
        and isinstance(plan.get("tasks"), list)
        and len(plan["tasks"]) >= 1
    )


def make_plan(request, llm, validation_retries=1, log=None):
    log = log if log is not None else []
    prompt = PLAN_PROMPT.format(request=request)
    raw = None
    for attempt in range(validation_retries + 1):
        raw = llm.complete(prompt)
        plan = extract_json(raw)
        if plan and _valid(plan):
            plan.setdefault("assumptions", [])
            log.append(f"plan accepted on attempt {attempt + 1}")
            return plan, raw
        log.append(f"plan attempt {attempt + 1} invalid (unparseable or failed schema check); retrying")
        prompt += "\nYour previous reply was not a valid plan JSON object. Reply with JSON only."
    log.append("LLM could not produce a valid plan; using deterministic fallback plan")
    return fallback_plan(request), raw


def fallback_plan(request):
    short = " ".join(request.split()[:10])
    return {
        "doc_type": "report",
        "title": f"Business Report: {short}",
        "assumptions": ["LLM did not return a valid plan; the built-in default report structure was used."],
        "tasks": [
            {"id": 1, "title": "Analyze request", "kind": "analyze", "detail": "Identify doc type and gaps"},
            {"id": 2, "title": "Draft sections", "kind": "draft", "detail": "Write each planned section"},
            {"id": 3, "title": "Review draft", "kind": "review", "detail": "Consistency and completeness check"},
            {"id": 4, "title": "Export document", "kind": "export", "detail": "Render the .docx"},
        ],
        "sections": [
            {"heading": "Executive Summary", "goal": "One-paragraph overview of the request and outcome"},
            {"heading": "Background", "goal": "Context inferred from the request"},
            {"heading": "Details", "goal": "Main body addressing the request"},
            {"heading": "Recommendations", "goal": "Actionable next steps"},
        ],
    }
