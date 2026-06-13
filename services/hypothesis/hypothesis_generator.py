from __future__ import annotations
import json
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import get_llm
from core.logger import logger
from core import metrics

PROMPT = """You are a senior ML researcher generating novel testable hypotheses.

IMPORTANT: Check the Research Memory below. DO NOT regenerate failed hypotheses.
Build on successes. Avoid known failure modes.

For each structural gap provided, generate ONE precise hypothesis.
Each must have:
- id, title, statement (falsifiable), motivation
- related_work (2-3 paper titles)
- novelty_score (1-10), feasibility_score (1-10)
- expected_impact (1-10), risk_score (1-10)
- expected_outcome
- scientist_score: weighted average = 0.35*novelty + 0.25*feasibility + 0.30*impact - 0.10*risk

Return ONLY valid JSON array."""

TREND_PROMPT = """Analyse these papers. Return JSON:
{"emerging":["method1"],"declining":["approach1"],"hot_intersections":["combo1"]}
Return ONLY valid JSON."""


class HypothesisGenerator:
    def __init__(self, kg=None):
        self._kg = kg

    def generate(self, literature_summary, graph_gaps, influential_papers, key_papers, memory_context="") -> Dict:
        logger.info(f"[HypothesisGenerator] {len(graph_gaps)} gaps, memory: {len(memory_context)} chars")

        gaps_text = "\n".join(
            f"- {g.get('description','')} (gap_score={g.get('gap_score',0)})"
            for g in graph_gaps[:8])

        influential_text = "\n".join(
            f"- {p.get('title','')} (citations:{p.get('citation_count',0)})"
            for p in influential_papers[:5])

        llm = get_llm(temperature=0.4)

        hyp_resp = llm.invoke([
            SystemMessage(content=PROMPT),
            HumanMessage(content=(
                f"Domain: {literature_summary[:500]}\n\n"
                f"Research Memory:\n{memory_context}\n\n"
                f"Structural gaps:\n{gaps_text}\n\n"
                f"Influential papers:\n{influential_text}"
            )),
        ])

        hypotheses = self._parse(hyp_resp.content, [])
        if not isinstance(hypotheses, list): hypotheses = []

        trends = {}
        if key_papers:
            papers_text = "\n".join(
                f"[{p.get('published','')[:10]}] {p.get('title','')}: {p.get('abstract','')[:200]}"
                for p in key_papers[:20])
            tr = llm.invoke([SystemMessage(content=TREND_PROMPT), HumanMessage(content=papers_text)])
            trends = self._parse(tr.content, {})

        metrics.inc("hypotheses_generated", len(hypotheses))
        return {"hypotheses": hypotheses, "trends": trends,
                "research_gaps": [g.get("description","") for g in graph_gaps[:8]]}

    @staticmethod
    def _parse(raw, default):
        raw = raw.strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith(("[","{")):
                    raw = part; break
        try: return json.loads(raw)
        except: return default
