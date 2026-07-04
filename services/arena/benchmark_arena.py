"""
Research Benchmark Arena — The Upgrade That Changes What's Possible

Instead of generating 3 hypotheses and calling it done, MARS generates
up to 100 ideas, scores each on 5 dimensions, and produces a ranked
leaderboard. This turns MARS from a report generator into a
Research Portfolio Manager.

Scoring dimensions per hypothesis:
  - novelty_score:      How new is this? (graph-gap magnitude + LLM)
  - feasibility_score:  Can a student do this in 4 weeks?
  - expected_impact:    If it works, how much does it matter?
  - compute_cost:       GPU-hours estimate (inverted — lower is better)
  - risk_score:         Probability of total failure

Scientist Score = 0.35*novelty + 0.25*feasibility + 0.30*impact
               - 0.10*risk  (cost already reflected in feasibility)

Arena also tracks:
  - Historical win rates per hypothesis type
  - Which gaps produce the highest-scoring ideas
  - Portfolio diversification (avoid clustering on one topic)
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import get_llm
from core.logger import logger
from core import config, metrics


BATCH_SCORE_PROMPT = """You are a research portfolio manager scoring hypotheses for prioritisation.

Score each hypothesis on these dimensions (1-10 each):
- novelty_score: How new is this? Does it combine things nobody has combined?
- feasibility_score: Can a grad student execute this in 4 weeks with 1 GPU?
- expected_impact: If it works, how much does it change the field?
- risk_score: Probability of complete failure (high risk = high score here)
- compute_cost_score: GPU cost (1=cheap/hours, 10=expensive/weeks)

Then compute:
  scientist_score = 0.35*novelty + 0.25*feasibility + 0.30*impact - 0.10*risk - 0.05*compute_cost

Also add:
- one_line_pitch: the hypothesis in 15 words for an investor
- killer_experiment: the single experiment that proves or disproves it fastest
- comparable_paper: a real paper this extends (title + year)

Return ONLY a JSON array, one object per hypothesis, preserving all original fields.
Add the score fields to each object."""


DIVERSITY_PROMPT = """Given this list of scored hypotheses, select the best PORTFOLIO of 5-8 ideas.
Avoid selecting more than 2 ideas from the same topic cluster.
Balance: at least 1 high-novelty (>8), 1 high-feasibility (>8), 1 high-impact (>8).

Return a JSON array of the selected hypothesis IDs only: ["id1", "id2", ...]"""


@dataclass
class ArenaEntry:
    id: str
    title: str
    statement: str
    domain: str
    novelty_score: float = 0.0
    feasibility_score: float = 0.0
    expected_impact: float = 0.0
    risk_score: float = 0.0
    compute_cost_score: float = 5.0
    scientist_score: float = 0.0
    one_line_pitch: str = ""
    killer_experiment: str = ""
    comparable_paper: str = ""
    debate_verdict: str = ""
    rank: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source_gap: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class BenchmarkArena:
    """
    Scores and ranks all generated hypotheses.
    Maintains a persistent leaderboard across sessions.
    """

    def __init__(self, arena_path: str | None = None):
        if arena_path is None:
            arena_path = str(Path(config.DATA_DIR) / "memory" / "arena_leaderboard.json")
        self._path = Path(arena_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._leaderboard: List[ArenaEntry] = []
        self._load()

    # ── Core scoring ────────────────────────────────────────────────────────

    def score_and_rank(self, hypotheses: List[dict], domain: str) -> Dict:
        """
        Score all hypotheses, add to leaderboard, return ranked results.

        Returns:
          ranked: List[dict] sorted by scientist_score DESC
          top_portfolio: List[dict] — diversified portfolio selection
          arena_stats: Dict — leaderboard statistics
        """
        if not hypotheses:
            return {"ranked": [], "top_portfolio": [], "arena_stats": {}}

        logger.info(f"[Arena] Scoring {len(hypotheses)} hypotheses")

        scored = self._batch_score(hypotheses, domain)
        ranked = sorted(scored, key=lambda x: x.get("scientist_score", 0), reverse=True)

        # Assign ranks
        for i, h in enumerate(ranked):
            h["rank"] = i + 1

        # Portfolio selection
        portfolio_ids = self._select_portfolio(ranked)
        top_portfolio = [h for h in ranked if h.get("id") in portfolio_ids]

        # Add to persistent leaderboard
        entries = [self._to_entry(h, domain) for h in ranked]
        self._leaderboard = self._merge(entries)
        self._save()

        arena_stats = self._compute_stats(ranked)
        logger.info(f"[Arena] Top: {ranked[0].get('title','?')} score={ranked[0].get('scientist_score',0):.2f}")

        return {
            "ranked": ranked,
            "top_portfolio": top_portfolio,
            "arena_stats": arena_stats,
        }

    def get_leaderboard(self, top_n: int = 20) -> List[dict]:
        """Return all-time top hypotheses across all sessions."""
        sorted_lb = sorted(self._leaderboard, key=lambda x: x.scientist_score, reverse=True)
        return [e.to_dict() for e in sorted_lb[:top_n]]

    def get_arena_stats(self) -> Dict:
        if not self._leaderboard:
            return {"total_scored": 0}
        scores = [e.scientist_score for e in self._leaderboard]
        return {
            "total_scored": len(self._leaderboard),
            "avg_scientist_score": round(sum(scores) / len(scores), 2),
            "max_scientist_score": round(max(scores), 2),
            "top_domain": self._top_domain(),
            "high_novelty_count": sum(1 for e in self._leaderboard if e.novelty_score >= 8),
            "high_feasibility_count": sum(1 for e in self._leaderboard if e.feasibility_score >= 8),
        }

    # ── Internal ─────────────────────────────────────────────────────────────

    def _batch_score(self, hypotheses: List[dict], domain: str) -> List[dict]:
        """Score in batches of 10 to stay within context limits."""
        all_scored = []
        batch_size = 10

        for i in range(0, len(hypotheses), batch_size):
            batch = hypotheses[i:i + batch_size]
            # Trim each hypothesis for context efficiency
            slim = [{"id": h.get("id",""), "title": h.get("title",""),
                     "statement": h.get("statement",""),
                     "motivation": h.get("motivation","")[:200],
                     "related_work": h.get("related_work",[])[:2],
                     "debate_verdict": h.get("debate_verdict","")}
                    for h in batch]

            llm = get_llm(temperature=0.1)
            resp = llm.invoke([
                SystemMessage(content=BATCH_SCORE_PROMPT),
                HumanMessage(content=f"Domain: {domain}\n\nHypotheses:\n{json.dumps(slim, indent=2)}"),
            ])

            scored_batch = self._parse_json(resp.content, [])
            if not isinstance(scored_batch, list):
                scored_batch = []

            # Merge scores back into original hypothesis dicts
            score_map = {s.get("id", ""): s for s in scored_batch}
            for hyp in batch:
                hid = hyp.get("id", "")
                enriched = {**hyp, **(score_map.get(hid, {}))}
                # Ensure scientist_score is computed
                if "scientist_score" not in enriched or not enriched["scientist_score"]:
                    n = enriched.get("novelty_score", 5)
                    f = enriched.get("feasibility_score", 5)
                    im = enriched.get("expected_impact", 5)
                    r = enriched.get("risk_score", 5)
                    c = enriched.get("compute_cost_score", 5)
                    enriched["scientist_score"] = round(
                        0.35*n + 0.25*f + 0.30*im - 0.10*r - 0.05*c, 2)
                all_scored.append(enriched)

        return all_scored

    def _select_portfolio(self, ranked: List[dict]) -> List[str]:
        if len(ranked) <= 5:
            return [h.get("id","") for h in ranked]

        # Quick heuristic: top by score but enforce diversity
        top = ranked[:min(20, len(ranked))]
        llm = get_llm(temperature=0.2)
        slim = [{"id": h.get("id",""), "title": h.get("title",""),
                 "novelty": h.get("novelty_score",0),
                 "feasibility": h.get("feasibility_score",0),
                 "impact": h.get("expected_impact",0),
                 "scientist_score": h.get("scientist_score",0)}
                for h in top]

        resp = llm.invoke([
            SystemMessage(content=DIVERSITY_PROMPT),
            HumanMessage(content=json.dumps(slim, indent=2)),
        ])
        ids = self._parse_json(resp.content, [])
        if isinstance(ids, list) and ids:
            return ids
        return [h.get("id","") for h in ranked[:5]]

    def _compute_stats(self, ranked: List[dict]) -> Dict:
        if not ranked:
            return {}
        scores = [h.get("scientist_score", 0) for h in ranked]
        return {
            "total_scored": len(ranked),
            "avg_score": round(sum(scores) / len(scores), 2),
            "max_score": round(max(scores), 2),
            "top_hypothesis": ranked[0].get("title", ""),
            "top_one_line_pitch": ranked[0].get("one_line_pitch", ""),
            "top_killer_experiment": ranked[0].get("killer_experiment", ""),
            "high_novelty": sum(1 for h in ranked if h.get("novelty_score", 0) >= 8),
            "high_feasibility": sum(1 for h in ranked if h.get("feasibility_score", 0) >= 8),
        }

    def _top_domain(self) -> str:
        if not self._leaderboard:
            return ""
        domains: dict = {}
        for e in self._leaderboard:
            domains[e.domain] = domains.get(e.domain, 0) + 1
        return max(domains, key=lambda x: domains[x])

    @staticmethod
    def _to_entry(h: dict, domain: str) -> ArenaEntry:
        return ArenaEntry(
            id=h.get("id", f"hyp_{int(time.time())}"),
            title=h.get("title", ""),
            statement=h.get("statement", ""),
            domain=domain,
            novelty_score=float(h.get("novelty_score", 0) or 0),
            feasibility_score=float(h.get("feasibility_score", 0) or 0),
            expected_impact=float(h.get("expected_impact", 0) or 0),
            risk_score=float(h.get("risk_score", 0) or 0),
            compute_cost_score=float(h.get("compute_cost_score", 5) or 5),
            scientist_score=float(h.get("scientist_score", 0) or 0),
            one_line_pitch=h.get("one_line_pitch", ""),
            killer_experiment=h.get("killer_experiment", ""),
            comparable_paper=h.get("comparable_paper", ""),
            debate_verdict=h.get("debate_verdict", ""),
        )

    def _merge(self, new_entries: List[ArenaEntry]) -> List[ArenaEntry]:
        existing_ids = {e.id for e in self._leaderboard}
        merged = list(self._leaderboard)
        for e in new_entries:
            if e.id not in existing_ids:
                merged.append(e)
        return merged

    def _save(self):
        data = [e.to_dict() for e in self._leaderboard]
        self._path.write_text(json.dumps(data, indent=2))

    def _load(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                self._leaderboard = [ArenaEntry(**d) for d in data]
                logger.info(f"[Arena] Loaded {len(self._leaderboard)} leaderboard entries")
            except Exception as exc:
                logger.warning(f"[Arena] Failed to load leaderboard: {exc}")

    @staticmethod
    def _parse_json(raw: str, default):
        import re
        raw = raw.strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith(("[", "{")):
                    raw = part
                    break
        try:
            return json.loads(raw)
        except Exception:
            pass
        # Extract first JSON array or object even if wrapped in prose
        for pattern in (r'\[[\s\S]*\]', r'\{[\s\S]*\}'):
            m = re.search(pattern, raw)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    continue
        return default
