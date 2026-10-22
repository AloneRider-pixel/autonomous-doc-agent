"""End-to-end tests. All run offline against the deterministic MockProvider."""
import os
from pathlib import Path

os.environ["AGENT_LLM"] = "mock"  # force the offline provider for the whole suite

from docx import Document
from fastapi.testclient import TestClient

from app.agent import Agent
from app.llm import LLMClient, MockProvider
from app.main import app

STANDARD_REQUEST = (
    "Create a project plan for migrating our internal company wiki to a new "
    "platform over 6 weeks."
)
COMPLEX_REQUEST = (
    "Prepare something for the board about the Q3 product thing - we may need "
    "budget numbers but Finance has not confirmed them, keep it short but make "
    "sure it covers everything, and we might present it Tuesday or maybe next month."
)


def _agent(tmp_path):
    return Agent(llm=LLMClient(providers=[MockProvider()]), out_dir=tmp_path)


def test_standard_request(tmp_path):
    r = _agent(tmp_path).run(STANDARD_REQUEST)
    assert r["doc_type"] == "project_plan"
    assert len(r["plan"]["tasks"]) >= 3
    assert len(r["plan"]["sections"]) >= 3
    doc = Document(r["document_path"])  # proves the .docx is a valid Word file
    styled = [(p.style.name, p.text) for p in doc.paragraphs]
    assert any(st == "Title" and r["title"] in txt for st, txt in styled)
    headings = [txt for st, txt in styled if st.startswith("Heading")]
    assert len(headings) >= 4


def test_complex_ambiguous_request(tmp_path):
    r = _agent(tmp_path).run(COMPLEX_REQUEST)
    # ambiguity must surface as recorded assumptions, not questions
    assert len(r["assumptions"]) >= 2
    assert any("board" in a.lower() or "ambiguous" in a.lower() for a in r["assumptions"])
    assert Path(r["document_path"]).exists()
    # trace shows the agent made and executed its own plan
    events = " ".join(s["event"] for s in r["steps"])
    assert "plan ready" in events and "exported" in events


def test_dirty_json_recovery(tmp_path):
    # provider returns the plan wrapped in prose + code fences; parser must recover
    agent = Agent(llm=LLMClient(providers=[MockProvider(dirty=True)]), out_dir=tmp_path)
    r = agent.run(STANDARD_REQUEST)
    assert "plan accepted on attempt 1" in " ".join(s["event"] for s in r["steps"])
    assert Path(r["document_path"]).exists()


def test_invalid_plan_fallback(tmp_path):
    class GarbageProvider(MockProvider):
        name = "garbage"
        def complete(self, prompt):
            if prompt.startswith("PLAN_JSON:"):
                return "I cannot help with that."
            return super().complete(prompt)
    agent = Agent(llm=LLMClient(providers=[GarbageProvider()]), out_dir=tmp_path)
    r = agent.run(STANDARD_REQUEST)
    assert "deterministic fallback plan" in " ".join(s["event"] for s in r["steps"])
    assert Path(r["document_path"]).exists()


def test_api_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    resp = client.post("/agent", json={"request": STANDARD_REQUEST})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ["request_id", "provider", "plan", "steps", "document_path", "download_url"]:
        assert key in body
    dl = client.get(body["download_url"])
    assert dl.status_code == 200
    assert dl.content[:2] == b"PK"  # a .docx is a zip


def test_api_rejects_empty_request():
    client = TestClient(app)
    assert client.post("/agent", json={"request": ""}).status_code == 422
