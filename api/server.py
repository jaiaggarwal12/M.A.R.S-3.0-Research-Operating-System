"""
M.A.R.S 3.0 FastAPI Server

POST /research               — full pipeline
POST /research/quick         — no experiments
GET  /metrics                — live benchmarks
GET  /memory                 — research memory entries
GET  /graph/network          — citation network JSON
GET  /graph/clusters         — research clusters
GET  /experiments            — generated experiment packages
GET  /experiments/{id}/files — list files for one experiment
POST /twin/build             — build a Research Twin persona
POST /twin/generate          — generate twin hypothesis
GET  /health
"""
from __future__ import annotations
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.pipeline import MARSPipeline
from core.logger import logger
from core import config, metrics

pipeline: Optional[MARSPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Do NOT init pipeline at startup — too heavy for free tier RAM.
    # It lazy-inits on the first /research request.
    logger.info("M.A.R.S 4.0 API starting (pipeline lazy-init on first request)")
    yield
    global pipeline
    if pipeline:
        pipeline.close()


app = FastAPI(
    title="M.A.R.S 3.0 — Research Operating System",
    description="Autonomous research: ingest → graph → memory → debate → experiment → analyze → report",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ── Request models ───────────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, example="speculative decoding LLM inference")
    domain: Optional[str] = None
    run_experiments: bool = True
    twin_persona: str = "Andrej Karpathy"

class TwinBuildRequest(BaseModel):
    name: str
    papers: List[dict]   # [{title, abstract, year}]

class TwinGenerateRequest(BaseModel):
    persona_name: str
    domain: str
    research_gaps: List[str] = []


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0"}


def _get_pipeline() -> MARSPipeline:
    """Lazy-init pipeline on first request — keeps startup RAM under 512MB."""
    global pipeline
    if pipeline is None:
        logger.info("Initializing M.A.R.S pipeline (first request)...")
        pipeline = MARSPipeline()
        logger.info("Pipeline ready")
    return pipeline


@app.get("/metrics")
async def get_metrics():
    """Live benchmark snapshot — real numbers."""
    return metrics.snapshot()


@app.post("/research")
async def run_research(req: ResearchRequest):
    try:
        p = _get_pipeline()
        result = p.run(
            req.query, req.domain or "",
            run_experiments=req.run_experiments,
            twin_persona=req.twin_persona,
        )
        bench = metrics.snapshot()
        return {
            "query": result["query"],
            "final_report": result.get("final_report", ""),
            "report_path": result.get("report_path", ""),
            "papers_indexed": result.get("papers_count", 0),
            "graph_nodes": result.get("graph_stats", {}).get("nodes", 0),
            "hypotheses_count": len(result.get("hypotheses", [])),
            "debate_transcript": result.get("debate_transcript", "")[:2000],
            "experiments_run": result.get("analysis", {}).get("summary_stats", {}).get("total", 0),
            "successful_discoveries": bench["successful_discoveries"],
            "research_gaps": result.get("research_gaps", []),
            "twin_hypothesis": result.get("twin_hypothesis", ""),
            "twin_persona": result.get("twin_persona", ""),
            "loop_iterations": len(result.get("loop_history", [])),
            "latency_sec": result.get("latency_sec", 0),
            "benchmarks": bench,
        }
    except Exception as exc:
        logger.exception(str(exc))
        raise HTTPException(500, str(exc))


@app.post("/research/quick")
async def run_quick(query: str):
    try:
        p = _get_pipeline()
        result = p.run(query, run_experiments=False)
        return {
            "query": query,
            "literature_summary": result.get("literature_summary", ""),
            "key_papers": result.get("key_papers", [])[:8],
            "research_gaps": result.get("research_gaps", []),
            "hypotheses": result.get("hypotheses", []),
        }
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/memory")
async def get_memory(domain: str = "", limit: int = 50):
    """Browse Research Memory DB."""
    p = _get_pipeline()
    all_entries = p.memory.all_entries()
    if domain:
        all_entries = [e for e in all_entries if domain.lower() in e.get("domain","").lower()]
    return {
        "total": p.memory.total(),
        "entries": all_entries[:limit],
        "successful": len(p.memory.get_successful_discoveries()),
        "failed": len(p.memory.get_failed_hypotheses()),
    }


@app.get("/graph/network")
async def graph_network(max_nodes: int = 120):
    p = _get_pipeline()
    return p.kg.get_citation_network_json(max_nodes=max_nodes)


@app.get("/graph/clusters")
async def graph_clusters():
    p = _get_pipeline()
    return {"clusters": p.kg.detect_research_clusters()}


@app.get("/graph/gaps")
async def graph_gaps():
    p = _get_pipeline()
    return {"gaps": p.kg.detect_gaps()}


@app.get("/experiments")
async def list_experiments():
    exp_dir = config.EXPERIMENTS_DIR
    if not os.path.exists(exp_dir):
        return {"experiments": [], "count": 0}
    exps = []
    for name in sorted(os.listdir(exp_dir)):
        p = os.path.join(exp_dir, name, "experiment_plan.json")
        if os.path.exists(p):
            try:
                exps.append(json.loads(open(p).read()))
            except Exception:
                pass
    return {"experiments": exps, "count": len(exps)}


@app.get("/experiments/{exp_id}/files")
async def experiment_files(exp_id: str):
    exp_path = Path(config.EXPERIMENTS_DIR) / exp_id
    if not exp_path.exists():
        raise HTTPException(404, "Experiment not found")
    files = {}
    for fname in ["train.py", "eval.py", "config.yaml", "requirements.txt", "Dockerfile", "README.md", "run_results.json"]:
        fp = exp_path / fname
        if fp.exists():
            try:
                files[fname] = fp.read_text()
            except Exception:
                files[fname] = "[binary or unreadable]"
    return {"experiment_id": exp_id, "files": files}


@app.post("/twin/build")
async def build_twin(req: TwinBuildRequest):
    try:
        p = _get_pipeline()
        persona = p.twin.build_persona(req.name, req.papers)
        return {"status": "ok", "persona": persona}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/twin/generate")
async def generate_twin(req: TwinGenerateRequest):
    p = _get_pipeline()
    if req.persona_name not in p.twin.list_personas():
        p.twin.load_famous_persona(req.persona_name)
    result = p.twin.generate_twin_hypothesis(
        req.persona_name, req.domain, req.research_gaps
    )
    return result


@app.get("/twin/personas")
async def list_personas():
    p = _get_pipeline()
    return {"personas": p.twin.list_personas()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host=config.API_HOST, port=config.API_PORT, reload=True)
