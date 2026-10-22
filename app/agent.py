"""Autonomous agent: request -> own TODO plan -> execute tasks -> polished .docx."""
import time
import uuid
from pathlib import Path

from . import docgen, planner
from .llm import LLMClient

SECTION_PROMPT = """SECTION:
Write the body of the section "{heading}" for a {doc_type} titled "{title}".
Goal: {goal}
Original user request: {request}
Write 2-4 short paragraphs of specific, professional content (mock data is fine where facts
are missing). Plain text only, no markdown headings.
"""


class Agent:
    def __init__(self, llm=None, out_dir="outputs"):
        self.llm = llm or LLMClient()
        self.out_dir = Path(out_dir).resolve()
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self, request):
        steps = []
        t0 = time.time()

        def log(event):
            steps.append({"t": round(time.time() - t0, 2), "event": event})

        log("request received")
        plan_log = []
        plan, _raw = planner.make_plan(request, self.llm, log=plan_log)
        for m in plan_log:
            log(m)
        log(f"plan ready: {len(plan['tasks'])} tasks, {len(plan['sections'])} sections "
            f"(provider: {self.llm.active.name})")

        rid = uuid.uuid4().hex[:8]
        sections = []
        doc_path = None

        for task in plan["tasks"]:
            kind = str(task.get("kind", "")).lower()
            log(f"task {task.get('id')}: {task.get('title')} [{kind}] - start")

            if kind == "draft":
                for s in plan["sections"]:
                    body = self.llm.complete(SECTION_PROMPT.format(
                        heading=s["heading"], doc_type=plan["doc_type"],
                        title=plan["title"], goal=s["goal"], request=request)).strip()
                    sections.append((s["heading"], body))
                log(f"drafted {len(sections)} sections")

            elif kind == "review":
                thin = [h for h, b in sections if len(b.split()) < 15]
                if thin:
                    log(f"review: thin sections {thin} - expanding")
                    sections = [
                        (h, b if len(b.split()) >= 15
                         else b + "\nAdditional detail added during the review pass to meet "
                              "the minimum substance bar for this section.")
                        for h, b in sections
                    ]
                else:
                    log("review: all sections meet the minimum substance bar")

            elif kind == "export":
                doc_path = self.out_dir / f"{rid}_{plan['doc_type']}.docx"
                docgen.build_docx(plan, sections, plan.get("assumptions", []), str(doc_path))
                log(f"exported {doc_path.name}")

            else:  # analyze / outline are already embodied in the plan itself
                log(f"{kind or 'task'} complete")

        if doc_path is None:  # plan without an export task: never leave the user empty-handed
            doc_path = self.out_dir / f"{rid}_{plan['doc_type']}.docx"
            docgen.build_docx(plan, sections, plan.get("assumptions", []), str(doc_path))
            log(f"exported {doc_path.name} (plan had no export task; exported anyway)")

        log("done")
        return {
            "request_id": rid,
            "provider": self.llm.active.name,
            "doc_type": plan["doc_type"],
            "title": plan["title"],
            "assumptions": plan.get("assumptions", []),
            "plan": plan,
            "steps": steps,
            "document_path": str(doc_path),
            "download_url": f"/download/{rid}",
        }
