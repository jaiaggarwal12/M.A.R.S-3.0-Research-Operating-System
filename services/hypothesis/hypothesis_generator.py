from __future__ import annotations
import json
import uuid
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import get_llm
from core.logger import logger
from core import metrics

PROMPT = """You are a senior ML researcher generating novel, testable hypotheses.

IMPORTANT:
- Check the Research Memory below. DO NOT regenerate failed hypotheses.
- The query/domain is the EXACT topic — generate hypotheses DIRECTLY about that topic.
- If structural gaps are provided, use them. If not, generate 3 hypotheses directly from the literature.

Each hypothesis must have these EXACT fields:
{
  "id": "hyp_<short_unique_slug>",
  "title": "short title",
  "statement": "falsifiable one-sentence claim",
  "motivation": "why this matters",
  "related_work": ["paper title 1", "paper title 2"],
  "novelty_score": <1-10>,
  "feasibility_score": <1-10>,
  "expected_impact": <1-10>,
  "risk_score": <1-10>,
  "scientist_score": <0.35*novelty + 0.25*feasibility + 0.30*impact - 0.10*risk>,
  "expected_outcome": "what success looks like",
  "evaluation_metrics": ["metric1", "metric2"],
  "required_baselines": ["baseline1"]
}

Return ONLY a valid JSON array of 3 hypothesis objects. No explanation."""

TREND_PROMPT = """Analyse these papers. Return JSON:
{"emerging":["method1"],"declining":["approach1"],"hot_intersections":["combo1"]}
Return ONLY valid JSON."""


class HypothesisGenerator:
    def __init__(self, kg=None):
        self._kg = kg

    def generate(self, literature_summary, graph_gaps, influential_papers,
                 key_papers, memory_context="", query="") -> Dict:
        logger.info(f"[HypothesisGenerator] {len(graph_gaps)} gaps, query='{query}'")

        gaps_text = "\n".join(
            f"- {g.get('description','')} (gap_score={g.get('gap_score',0)})"
            for g in graph_gaps[:8]) or "No structural gaps detected — generate hypotheses directly from the literature and domain."

        influential_text = "\n".join(
            f"- {p.get('title','')} (citations:{p.get('citation_count',0)})"
            for p in influential_papers[:5]) or "No influential papers found."

        llm = get_llm(temperature=0.4)

        hyp_resp = llm.invoke([
            SystemMessage(content=PROMPT),
            HumanMessage(content=(
                f"Research Topic / Domain: {query or literature_summary[:200]}\n\n"
                f"Literature Summary:\n{literature_summary[:600]}\n\n"
                f"Research Memory (avoid repeating these):\n{memory_context or 'None'}\n\n"
                f"Structural gaps:\n{gaps_text}\n\n"
                f"Influential papers:\n{influential_text}"
            )),
        ])

        hypotheses = self._parse(hyp_resp.content, [])
        if not isinstance(hypotheses, list):
            hypotheses = []

        # Ensure every hypothesis has a valid id
        for h in hypotheses:
            if not h.get("id"):
                h["id"] = f"hyp_{uuid.uuid4().hex[:8]}"
            # Ensure scientist_score is computed if missing
            if not h.get("scientist_score"):
                n = h.get("novelty_score", 5)
                f_ = h.get("feasibility_score", 5)
                i = h.get("expected_impact", 5)
                r = h.get("risk_score", 5)
                h["scientist_score"] = round(0.35*n + 0.25*f_ + 0.30*i - 0.10*r, 2)

        trends = {}
        if key_papers:
            papers_text = "\n".join(
                f"[{p.get('published','')[:10]}] {p.get('title','')}: {p.get('abstract','')[:200]}"
                for p in key_papers[:15])
            tr = llm.invoke([SystemMessage(content=TREND_PROMPT), HumanMessage(content=papers_text)])
            trends = self._parse(tr.content, {})

        logger.info(f"[HypothesisGenerator] Generated {len(hypotheses)} hypotheses")
        metrics.inc("hypotheses_generated", len(hypotheses))
        return {"hypotheses": hypotheses, "trends": trends,
                "research_gaps": [g.get("description","") for g in graph_gaps[:8]]}

    @staticmethod
    def _parse(raw, default):
        import re
        raw = raw.strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith(("[","{")):
                    raw = part; break
        try:
            return json.loads(raw)
        except:
            pass
        # Extract first JSON array or object even if wrapped in text
        for pattern in (r'\[[\s\S]*\]', r'\{[\s\S]*\}'):
            m = re.search(pattern, raw)
            if m:
                try:
                    return json.loads(m.group())
                except:
                    continue
        return default
