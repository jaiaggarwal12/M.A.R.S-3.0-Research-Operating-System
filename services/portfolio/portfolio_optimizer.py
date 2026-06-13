"""
Research Portfolio Optimizer

Thinks like a venture capital fund, not a ranking list.

Instead of: "Here's the top idea, go do it."

Portfolio logic:
  - High risk / high reward  (moonshot)   — 1 bet
  - Medium risk / solid ROI  (core)       — 2-3 bets
  - Low risk / fast result   (quick win)  — 1-2 bets

Constraints:
  - Total compute budget (GPU hours)
  - Max 2 experiments in same topic cluster (diversification)
  - At least 1 experiment runnable without GPU
  - Minimum novelty threshold (don't waste compute on obvious work)

Also provides:
  - Risk-adjusted return: expected_impact * success_probability
  - Compute ROI: expected_impact / compute_cost
  - Portfolio Sharpe ratio analogue: mean(risk_adj) / std(risk_adj)
  - Rebalancing suggestions based on what succeeded/failed

This framing — "research as portfolio management" — is extremely rare
in student projects and maps directly to how research labs actually
allocate compute budgets.
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import get_llm
from core.logger import logger


PORTFOLIO_PROMPT = """You are a research portfolio manager allocating a compute budget.

Given scored hypotheses with risk/reward profiles, construct the optimal research portfolio.

Portfolio requirements:
- EXACTLY 1 moonshot: novelty >= 8, risk >= 7, potential is transformative
- 2-3 core bets: balanced novelty/feasibility, likely to produce results
- 1-2 quick wins: feasibility >= 7, can run without GPU, produces results fast

Additional constraints:
- No more than 2 experiments from the same topic cluster
- Total estimated compute <= budget_gpu_hours
- At least 1 experiment with feasibility >= 8 (guaranteed to run)

For each selected experiment, provide:
- slot: "moonshot" | "core" | "quick_win"
- rationale: why this fits this portfolio slot
- success_probability: 0.0-1.0 (your estimate)
- risk_adjusted_return: success_probability * expected_impact
- compute_roi: expected_impact / max(compute_cost_score, 1)
- execution_order: 1, 2, 3... (run quick wins first to validate direction)
- compute_allocation_hrs: recommended GPU hours for this experiment

Return JSON:
{
  "portfolio": [
    {
      "hypothesis_id": "...",
      "title": "...",
      "slot": "moonshot|core|quick_win",
      "rationale": "...",
      "success_probability": 0.0-1.0,
      "risk_adjusted_return": 0.0-10.0,
      "compute_roi": 0.0-10.0,
      "execution_order": 1,
      "compute_allocation_hrs": 4.0
    }
  ],
  "portfolio_stats": {
    "expected_value": "weighted sum of risk_adj_return",
    "total_compute_hrs": "sum",
    "diversification_score": 0.0-1.0,
    "sharpe_analogue": "mean/std of risk_adj_returns",
    "portfolio_rationale": "2-sentence summary of the allocation strategy"
  },
  "excluded": [
    {"hypothesis_id": "...", "reason": "why excluded"}
  ],
  "rebalancing_triggers": [
    "If moonshot fails within 2 iterations, pivot to ...",
    "If quick win shows >X% improvement, double down by ..."
  ]
}"""


@dataclass
class PortfolioSlot:
    hypothesis_id: str
    title: str
    slot: str              # moonshot | core | quick_win
    rationale: str
    success_probability: float
    risk_adjusted_return: float
    compute_roi: float
    execution_order: int
    compute_allocation_hrs: float
    novelty_score: float = 0.0
    feasibility_score: float = 0.0
    expected_impact: float = 0.0
    scientist_score: float = 0.0

    def to_dict(self): return asdict(self)


@dataclass
class Portfolio:
    slots: List[PortfolioSlot]
    stats: Dict
    excluded: List[Dict]
    rebalancing_triggers: List[str]
    budget_gpu_hours: float

    def moonshots(self) -> List[PortfolioSlot]:
        return [s for s in self.slots if s.slot == "moonshot"]

    def core_bets(self) -> List[PortfolioSlot]:
        return [s for s in self.slots if s.slot == "core"]

    def quick_wins(self) -> List[PortfolioSlot]:
        return [s for s in self.slots if s.slot == "quick_win"]

    def execution_order(self) -> List[PortfolioSlot]:
        return sorted(self.slots, key=lambda x: x.execution_order)

    def to_dict(self) -> dict:
        return {
            "slots": [s.to_dict() for s in self.slots],
            "stats": self.stats,
            "excluded": self.excluded,
            "rebalancing_triggers": self.rebalancing_triggers,
            "budget_gpu_hours": self.budget_gpu_hours,
            "moonshots": len(self.moonshots()),
            "core_bets": len(self.core_bets()),
            "quick_wins": len(self.quick_wins()),
        }

    def summary_markdown(self) -> str:
        md = f"## Research Portfolio\n\n"
        md += f"**Budget:** {self.budget_gpu_hours} GPU hours | "
        md += f"**Expected value:** {self.stats.get('expected_value','?')} | "
        md += f"**Sharpe:** {self.stats.get('sharpe_analogue','?')}\n\n"
        md += f"*{self.stats.get('portfolio_rationale','')}*\n\n"

        for slot_name, emoji, slots in [
            ("🚀 Moonshot", "🚀", self.moonshots()),
            ("🎯 Core Bets", "🎯", self.core_bets()),
            ("⚡ Quick Wins", "⚡", self.quick_wins()),
        ]:
            if not slots: continue
            md += f"### {slot_name}\n"
            for s in slots:
                md += (f"**{s.execution_order}. {s.title}**\n"
                       f"P(success)={s.success_probability:.0%} | "
                       f"Risk-adj return={s.risk_adjusted_return:.1f} | "
                       f"Compute ROI={s.compute_roi:.1f} | "
                       f"~{s.compute_allocation_hrs}h GPU\n"
                       f"_{s.rationale}_\n\n")

        if self.rebalancing_triggers:
            md += "### Rebalancing Triggers\n"
            for t in self.rebalancing_triggers:
                md += f"- {t}\n"

        if self.excluded:
            md += f"\n*{len(self.excluded)} hypotheses excluded (budget/diversification)*\n"

        return md


class PortfolioOptimizer:
    """
    VC-style research portfolio construction.
    Takes the Arena leaderboard and constructs an optimal allocation.
    """

    def optimize(
        self,
        ranked_hypotheses: List[dict],
        budget_gpu_hours: float = 20.0,
        prior_results: Optional[List[dict]] = None,
    ) -> Portfolio:
        """
        Build optimal research portfolio from ranked hypotheses.

        Args:
            ranked_hypotheses: Arena-ranked list with scientist_scores
            budget_gpu_hours: Total compute budget
            prior_results: Past experiment results for rebalancing
        """
        if not ranked_hypotheses:
            return Portfolio(slots=[], stats={}, excluded=[], rebalancing_triggers=[],
                             budget_gpu_hours=budget_gpu_hours)

        logger.info(f"[Portfolio] Optimizing {len(ranked_hypotheses)} candidates, "
                    f"budget={budget_gpu_hours}h")

        # Pre-filter: only hypotheses that passed debate
        candidates = [h for h in ranked_hypotheses
                      if h.get("debate_verdict") != "no-go"]

        if not candidates:
            candidates = ranked_hypotheses  # fallback if all flagged

        # Build slim context for LLM
        slim = [
            {
                "id": h.get("id", ""),
                "title": h.get("title", "")[:60],
                "novelty_score": h.get("novelty_score", 5),
                "feasibility_score": h.get("feasibility_score", 5),
                "expected_impact": h.get("expected_impact", 5),
                "risk_score": h.get("risk_score", 5),
                "compute_cost_score": h.get("compute_cost_score", 5),
                "scientist_score": h.get("scientist_score", 5),
                "debate_verdict": h.get("debate_verdict", "conditional"),
                "estimated_compute": h.get("estimated_compute", "~4h"),
            }
            for h in candidates[:20]  # top 20 to context
        ]

        prior_ctx = ""
        if prior_results:
            prior_ctx = "\n\nPrior experiment outcomes:\n" + "\n".join(
                f"- {r.get('title','?')}: {r.get('hypothesis_verdict','?')} — {r.get('key_finding','')[:80]}"
                for r in prior_results[:5]
            )

        llm = get_llm(temperature=0.2)
        resp = llm.invoke([
            SystemMessage(content=PORTFOLIO_PROMPT),
            HumanMessage(content=(
                f"Budget: {budget_gpu_hours} GPU hours\n\n"
                f"Candidates:\n{json.dumps(slim, indent=2)}"
                f"{prior_ctx}"
            )),
        ])

        parsed = self._parse_json(resp.content)
        portfolio_data = parsed.get("portfolio", [])
        stats = parsed.get("portfolio_stats", {})
        excluded = parsed.get("excluded", [])
        rebalancing = parsed.get("rebalancing_triggers", [])

        # Map back to full hypothesis data
        hyp_map = {h.get("id", ""): h for h in ranked_hypotheses}
        slots = []
        for item in portfolio_data:
            hid = item.get("hypothesis_id", "")
            hyp = hyp_map.get(hid, {})
            slots.append(PortfolioSlot(
                hypothesis_id=hid,
                title=item.get("title", hyp.get("title", "")),
                slot=item.get("slot", "core"),
                rationale=item.get("rationale", ""),
                success_probability=float(item.get("success_probability", 0.5)),
                risk_adjusted_return=float(item.get("risk_adjusted_return", 0)),
                compute_roi=float(item.get("compute_roi", 0)),
                execution_order=int(item.get("execution_order", 99)),
                compute_allocation_hrs=float(item.get("compute_allocation_hrs", 4.0)),
                novelty_score=float(hyp.get("novelty_score", 0)),
                feasibility_score=float(hyp.get("feasibility_score", 0)),
                expected_impact=float(hyp.get("expected_impact", 0)),
                scientist_score=float(hyp.get("scientist_score", 0)),
            ))

        # Compute stats if LLM missed them
        if slots and not stats.get("sharpe_analogue"):
            rar = [s.risk_adjusted_return for s in slots]
            mean_rar = sum(rar) / len(rar)
            std_rar = math.sqrt(sum((x - mean_rar) ** 2 for x in rar) / max(len(rar) - 1, 1))
            stats["sharpe_analogue"] = round(mean_rar / max(std_rar, 0.01), 2)
            stats["expected_value"] = round(sum(rar), 2)
            stats["total_compute_hrs"] = sum(s.compute_allocation_hrs for s in slots)

        portfolio = Portfolio(
            slots=slots,
            stats=stats,
            excluded=excluded,
            rebalancing_triggers=rebalancing,
            budget_gpu_hours=budget_gpu_hours,
        )

        logger.info(f"[Portfolio] Built: {len(portfolio.moonshots())} moonshots, "
                    f"{len(portfolio.core_bets())} core, {len(portfolio.quick_wins())} quick wins")
        return portfolio

    def suggest_rebalance(
        self,
        current_portfolio: Portfolio,
        completed_results: List[dict],
    ) -> Dict:
        """
        After some experiments complete, suggest rebalancing.
        E.g.: "Moonshot failed → pivot budget to core bet #2"
        """
        if not completed_results:
            return {"action": "continue", "reason": "No results yet"}

        failed = [r for r in completed_results if r.get("hypothesis_verdict") == "rejected"]
        confirmed = [r for r in completed_results if r.get("hypothesis_verdict") == "confirmed"]

        if not failed and not confirmed:
            return {"action": "continue", "reason": "Results inconclusive — gather more data"}

        if any(s.slot == "moonshot" for s in current_portfolio.slots):
            moonshot_id = current_portfolio.moonshots()[0].hypothesis_id if current_portfolio.moonshots() else None
            if any(r.get("experiment_id", "").startswith(moonshot_id or "X") for r in failed):
                return {
                    "action": "pivot",
                    "reason": "Moonshot failed — reallocate budget to highest core bet",
                    "redirect_hours": sum(
                        s.compute_allocation_hrs for s in current_portfolio.moonshots()),
                    "redirect_to": (current_portfolio.core_bets()[0].title
                                    if current_portfolio.core_bets() else "next best core"),
                }

        if confirmed:
            return {
                "action": "double_down",
                "reason": f"Confirmed result: '{confirmed[0].get('key_finding','')[:80]}' — allocate more compute",
                "hypothesis": confirmed[0].get("experiment_id", ""),
            }

        return {"action": "continue", "reason": "Mixed results — run remaining experiments"}

    @staticmethod
    def _parse_json(raw: str) -> dict:
        raw = raw.strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("{"):
                    raw = part
                    break
        try:
            return json.loads(raw)
        except Exception:
            return {}
