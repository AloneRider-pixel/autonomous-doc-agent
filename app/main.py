"""FastAPI surface for the autonomous document agent."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .agent import Agent

app = FastAPI(title="Autonomous Doc Agent", version="1.0.0")
agent = Agent()


class AgentRequest(BaseModel):
    request: str = Field(..., min_length=5, description="Natural-language document request")


class AgentResponse(BaseModel):
    request_id: str
    provider: str
    doc_type: str
    title: str
    assumptions: list
    plan: dict
    steps: list
    document_path: str
    download_url: str


@app.get("/health")
def health():
    return {"status": "ok", "provider": agent.llm.active.name}


@app.post("/agent", response_model=AgentResponse)
def run_agent(body: AgentRequest):
    return agent.run(body.request)


@app.get("/download/{request_id}")
def download(request_id: str):
    matches = list(agent.out_dir.glob(f"{request_id}_*.docx"))
    if not matches:
        raise HTTPException(status_code=404, detail="document not found")
    return FileResponse(matches[0], filename=matches[0].name)
