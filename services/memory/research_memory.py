"""
Research Memory DB — Upgrade 1

Persistent store of every hypothesis tried, result, failure reason,
confidence, date, and paper sources.

Next time an agent generates a hypothesis, it checks memory first:
"Already failed with reason: overfitting on small dataset."

Uses TinyDB (JSON file, zero config) with SQLite fallback for queries.

Schema per entry:
{
  "id": "hyp_42",
  "hypothesis": "Use MoE routing for feed ranking",
  "domain": "recommendation systems",
  "status": "failed|success|running|designed",
  "result_summary": "−1.2% AUC vs baseline",
  "failure_reason": "Overfitting on small dataset",
  "confidence_before": 7.2,
  "confidence_after": 2.1,
  "novelty_score": 8.5,
  "paper_sources": ["arxiv:2401.xxxxx"],
  "metrics": {"auc": 0.812, "baseline_auc": 0.824},
  "created_at": "2024-06-01T12:00:00",
  "updated_at": "2024-06-01T14:30:00",
  "loop_iteration": 1,
  "experiment_id": "moe_feed_ranking_12345",
}
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from core.logger import logger
from core import config, metrics

try:
    from tinydb import TinyDB, Query
    _TINYDB = True
except ImportError:
    _TINYDB = False
    logger.warning("tinydb not installed — using in-memory dict store")


class ResearchMemory:
    """
    Persistent research memory. Agents query this before generating hypotheses
    to avoid repeating failed work and build on successful experiments.
    """

    def __init__(self, db_path: str = config.MEMORY_DB_PATH):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fallback: List[dict] = []

        if _TINYDB:
            self._db = TinyDB(str(self._path))
            self._table = self._db.table("hypotheses")
        else:
            self._db = None
            self._table = None

        logger.info(f"ResearchMemory initialised ({self.total()} existing entries)")

    # ── Write ───────────────────────────────────────────────────────────────

    def add_hypothesis(
        self,
        hypothesis: str,
        domain: str,
        novelty_score: float = 0.0,
        feasibility_score: float = 0.0,
        paper_sources: List[str] | None = None,
        loop_iteration: int = 0,
    ) -> str:
        """Record a new hypothesis. Returns its ID."""
        entry_id = f"hyp_{uuid.uuid4().hex[:8]}"
        entry = {
            "id": entry_id,
            "hypothesis": hypothesis,
            "domain": domain,
            "status": "designed",
            "result_summary": "",
            "failure_reason": "",
            "confidence_before": novelty_score,
            "confidence_after": 0.0,
            "novelty_score": novelty_score,
            "feasibility_score": feasibility_score,
            "paper_sources": paper_sources or [],
            "metrics": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "loop_iteration": loop_iteration,
            "experiment_id": "",
            "debate_verdict": "",
        }
        self._write(entry)
        metrics.inc("memory_entries")
        return entry_id

    def update_result(
        self,
        entry_id: str,
        status: str,                      # "success" | "failed" | "inconclusive"
        result_summary: str,
        failure_reason: str = "",
        metrics_dict: dict | None = None,
        confidence_after: float = 0.0,
        experiment_id: str = "",
    ):
        """Update a hypothesis entry after experiment completion."""
        update = {
            "status": status,
            "result_summary": result_summary,
            "failure_reason": failure_reason,
            "metrics": metrics_dict or {},
            "confidence_after": confidence_after,
            "experiment_id": experiment_id,
            "updated_at": datetime.now().isoformat(),
        }
        self._update(entry_id, update)
        if status == "success":
            metrics.inc("successful_discoveries")

    def add_debate_verdict(self, entry_id: str, verdict: str):
        self._update(entry_id, {"debate_verdict": verdict, "updated_at": datetime.now().isoformat()})

    # ── Query ────────────────────────────────────────────────────────────────

    def get_relevant_memory(self, domain: str, hypothesis_text: str, top_k: int = 5) -> List[dict]:
        """
        Return past entries most relevant to current domain and hypothesis.
        Used by agents to avoid repeating failed work.
        """
        all_entries = self._read_all()
        domain_entries = [
            e for e in all_entries
            if domain.lower() in e.get("domain", "").lower()
            or any(word in e.get("hypothesis", "").lower()
                   for word in hypothesis_text.lower().split()[:5])
        ]
        # Sort: failures first (so agent learns what NOT to do), then successes
        domain_entries.sort(key=lambda x: (
            0 if x.get("status") == "failed" else
            1 if x.get("status") == "success" else 2
        ))
        return domain_entries[:top_k]

    def get_failed_hypotheses(self, domain: str = "") -> List[dict]:
        all_entries = self._read_all()
        return [
            e for e in all_entries
            if e.get("status") == "failed"
            and (not domain or domain.lower() in e.get("domain", "").lower())
        ]

    def get_successful_discoveries(self) -> List[dict]:
        return [e for e in self._read_all() if e.get("status") == "success"]

    def format_memory_context(self, entries: List[dict]) -> str:
        """Format memory entries as a context string for LLM prompts."""
        if not entries:
            return "No relevant prior experiments found."
        lines = ["RESEARCH MEMORY — Prior experiments in this domain:\n"]
        for e in entries:
            status_emoji = {"success": "✅", "failed": "❌", "inconclusive": "⚠️"}.get(e.get("status",""), "❓")
            lines.append(
                f"{status_emoji} [{e['id']}] {e['hypothesis']}\n"
                f"   Status: {e['status']} | Result: {e.get('result_summary','—')}\n"
                f"   {'Failure reason: ' + e['failure_reason'] if e.get('failure_reason') else ''}\n"
            )
        return "\n".join(lines)

    def total(self) -> int:
        return len(self._read_all())

    def all_entries(self) -> List[dict]:
        return self._read_all()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _write(self, entry: dict):
        if self._table is not None:
            self._table.insert(entry)
        else:
            self._fallback.append(entry)

    def _update(self, entry_id: str, update: dict):
        if self._table is not None:
            Q = Query()
            self._table.update(update, Q.id == entry_id)
        else:
            for e in self._fallback:
                if e.get("id") == entry_id:
                    e.update(update)
                    break

    def _read_all(self) -> List[dict]:
        if self._table is not None:
            return self._table.all()
        return self._fallback
