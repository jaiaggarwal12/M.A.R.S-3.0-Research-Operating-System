"""
Research Twin — Upgrade 9

Upload papers from a researcher (Andrew Ng, Yann LeCun, etc.) and MARS
learns their style, topic preferences, and reasoning patterns.

Then generates hypotheses "as that researcher might."

This is a memorable, unique demo feature.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import get_llm
from core.logger import logger
from core import config


PERSONA_BUILD_PROMPT = """Analyse these paper titles, abstracts and topics from a researcher's body of work.
Extract their intellectual DNA:
1. Core research themes (top 5)
2. Preferred methodologies
3. Writing/reasoning style (2-3 sentences)
4. Typical problem framing approach
5. What kind of problems they're drawn to
6. Signature phrases or concepts they use

Return as JSON:
{
  "name": "researcher name",
  "core_themes": [...],
  "methodologies": [...],
  "style": "...",
  "problem_framing": "...",
  "drawn_to": "...",
  "signature_concepts": [...]
}"""


TWIN_HYPOTHESIS_PROMPT = """You are roleplaying as {name}, the ML researcher.
Based on their intellectual style:
  Core themes: {themes}
  Methodologies: {methods}
  Style: {style}
  Drawn to: {drawn_to}

Given this research domain: {domain}
And these research gaps: {gaps}

Generate ONE hypothesis as {name} might — using their vocabulary, framing, and approach.
Then explain: "Why {name} would find this interesting."

Format:
HYPOTHESIS: <statement>
REASONING: <why this fits their style>
SIGNATURE_MOVE: <the technique they'd use, in their style>"""


class ResearchTwin:
    """
    Builds a persona from uploaded papers and generates hypotheses
    in that researcher's style.
    """

    def __init__(self, papers_dir: str = config.TWIN_PAPERS_DIR):
        self.papers_dir = Path(papers_dir)
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self._personas: Dict[str, dict] = {}
        self._load_saved_personas()

    def build_persona(self, name: str, papers: List[dict]) -> dict:
        """
        Build a researcher persona from their papers.
        papers: list of {title, abstract, year}
        """
        logger.info(f"[ResearchTwin] Building persona for: {name}")

        papers_text = "\n\n".join(
            f"[{p.get('year', '')}] {p.get('title', '')}\n{p.get('abstract', '')[:300]}"
            for p in papers[:20]
        )

        llm = get_llm(temperature=0.2)
        response = llm.invoke([
            SystemMessage(content=PERSONA_BUILD_PROMPT),
            HumanMessage(content=f"Researcher: {name}\n\nPapers:\n{papers_text}"),
        ])

        try:
            raw = response.content.strip()
            if "```" in raw:
                for part in raw.split("```"):
                    part = part.strip().lstrip("json").strip()
                    if part.startswith("{"):
                        raw = part
                        break
            persona = json.loads(raw)
            persona["name"] = name
            persona["paper_count"] = len(papers)
        except Exception:
            persona = {
                "name": name,
                "core_themes": [],
                "methodologies": [],
                "style": f"Analytical, precise, {name}'s approach",
                "problem_framing": "First principles",
                "drawn_to": "Novel architectural innovations",
                "signature_concepts": [],
                "paper_count": len(papers),
            }

        self._personas[name] = persona
        self._save_persona(name, persona)
        logger.info(f"[ResearchTwin] Persona built for {name}: {persona.get('core_themes','')[:3]}")
        return persona

    def generate_twin_hypothesis(
        self,
        persona_name: str,
        domain: str,
        research_gaps: List[str],
    ) -> Dict:
        """Generate a hypothesis as this researcher would."""
        persona = self._personas.get(persona_name)
        if not persona:
            return {"twin_persona": persona_name, "twin_hypothesis": "Persona not found. Build it first."}

        gaps_text = "\n".join(f"- {g}" for g in research_gaps[:5])
        llm = get_llm(temperature=0.5)

        response = llm.invoke([
            HumanMessage(content=TWIN_HYPOTHESIS_PROMPT.format(
                name=persona["name"],
                themes=", ".join(persona.get("core_themes", [])[:4]),
                methods=", ".join(persona.get("methodologies", [])[:3]),
                style=persona.get("style", ""),
                drawn_to=persona.get("drawn_to", ""),
                domain=domain,
                gaps=gaps_text,
            )),
        ])

        return {
            "twin_persona": persona_name,
            "twin_hypothesis": response.content,
            "persona_summary": persona,
        }

    def list_personas(self) -> List[str]:
        return list(self._personas.keys())

    def get_persona(self, name: str) -> Optional[dict]:
        return self._personas.get(name)

    # ── Prebuilt famous personas (demo-ready, no paper upload needed) ───────

    def load_famous_persona(self, name: str) -> dict:
        """
        Pre-built personas for demo purposes.
        In production, replace with real paper analysis.
        """
        famous = {
            "Andrew Ng": {
                "name": "Andrew Ng",
                "core_themes": ["transfer learning", "deep learning education", "AI for everyone", "unsupervised learning", "neural networks"],
                "methodologies": ["empirical validation", "simple baselines first", "learning curves analysis"],
                "style": "Pragmatic, pedagogically clear, focuses on practical impact. Builds intuition before math.",
                "problem_framing": "How can this technique be made accessible and applicable at scale?",
                "drawn_to": "Methods that democratise AI, transfer learning, reducing labelled data requirements",
                "signature_concepts": ["learning curves", "bias-variance tradeoff", "data-centric AI"],
                "paper_count": 0,
            },
            "Yann LeCun": {
                "name": "Yann LeCun",
                "core_themes": ["self-supervised learning", "world models", "energy-based models", "convolutional networks", "joint embedding architectures"],
                "methodologies": ["architectural innovation", "theoretical grounding", "large-scale empirical study"],
                "style": "Provocative, architectural-first thinking. Challenges consensus. Long-horizon vision.",
                "problem_framing": "What's the fundamental architectural principle missing from current systems?",
                "drawn_to": "World models, predictive learning, autonomous AI that doesn't need labels",
                "signature_concepts": ["Joint Embedding Predictive Architecture", "Energy-Based Models", "V-JEPA"],
                "paper_count": 0,
            },
            "Andrej Karpathy": {
                "name": "Andrej Karpathy",
                "core_themes": ["neural network interpretability", "LLM internals", "computer vision", "autonomous driving", "software 2.0"],
                "methodologies": ["build from scratch to understand", "visualisation-first", "minimal clean implementations"],
                "style": "Engineering clarity. Builds intuition through minimal implementations. Educator instincts.",
                "problem_framing": "How does this actually work inside? What's the simplest version that captures the idea?",
                "drawn_to": "Understanding what neural networks learn, scaling laws, LLM tokenisation quirks",
                "signature_concepts": ["Software 2.0", "recurrent networks as programs", "attention visualisation"],
                "paper_count": 0,
            },
        }
        if name in famous:
            self._personas[name] = famous[name]
            return famous[name]
        return {}

    def _save_persona(self, name: str, persona: dict):
        path = self.papers_dir / f"persona_{name.replace(' ','_').lower()}.json"
        path.write_text(json.dumps(persona, indent=2))

    def _load_saved_personas(self):
        for path in self.papers_dir.glob("persona_*.json"):
            try:
                persona = json.loads(path.read_text())
                self._personas[persona.get("name", path.stem)] = persona
            except Exception:
                pass
