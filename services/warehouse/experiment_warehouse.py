"""
Experiment Warehouse

Stores every experiment, metric, failure, and paper as nodes in a
research tree. Answers the question: "What has MARS learned so far?"

Tree structure:
  Root: Research Domain
  ├── Branch: Hypothesis cluster A
  │   ├── Experiment 1 (failed — overfitting)
  │   ├── Experiment 2 (success — +4% accuracy)
  │   └── Experiment 3 (branch — new direction from success)
  └── Branch: Hypothesis cluster B
      └── Experiment 4 (running)

This makes the research history navigable and memorable.
A professor opening this and seeing a branching research tree of
real experiments is not going to think "basic student project."

Also provides:
  - Failure pattern detection (what kinds of hypotheses keep failing?)
  - Success pattern extraction (what worked? why?)
  - Lineage tracking (experiment 3 was born from experiment 2's results)
"""
from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from core.logger import logger
from core import config


@dataclass
class ExperimentNode:
    node_id: str
    parent_id: Optional[str]          # None = root
    experiment_id: str
    title: str
    hypothesis: str
    status: str                        # designed | running | success | failed | inconclusive
    metrics: Dict = field(default_factory=dict)
    failure_reason: str = ""
    key_finding: str = ""
    source: str = "standard"           # standard | cross_paper | twin | loop
    depth: int = 0                     # 0 = first iteration, 1 = spawned from result, etc.
    domain: str = ""
    scientist_score: float = 0.0
    hypothesis_verdict: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    children: List[str] = field(default_factory=list)  # child node_ids

    def to_dict(self) -> dict:
        return asdict(self)


class ExperimentWarehouse:
    """
    Persistent tree of all experiments across all sessions.
    Provides research tree visualisation data and pattern analysis.
    """

    def __init__(self, warehouse_path: str | None = None):
        if warehouse_path is None:
            warehouse_path = str(Path(config.DATA_DIR) / "memory" / "experiment_warehouse.json")
        self._path = Path(warehouse_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._nodes: Dict[str, ExperimentNode] = {}
        self._roots: List[str] = []   # top-level domain node IDs
        self._load()

    # ── Write ────────────────────────────────────────────────────────────────

    def add_experiment(
        self,
        experiment_id: str,
        title: str,
        hypothesis: str,
        domain: str,
        parent_id: Optional[str] = None,
        source: str = "standard",
        depth: int = 0,
        scientist_score: float = 0.0,
    ) -> str:
        """Add a new experiment node. Returns node_id."""
        node_id = f"node_{uuid.uuid4().hex[:8]}"
        node = ExperimentNode(
            node_id=node_id,
            parent_id=parent_id,
            experiment_id=experiment_id,
            title=title,
            hypothesis=hypothesis,
            status="designed",
            source=source,
            depth=depth,
            domain=domain,
            scientist_score=scientist_score,
        )
        self._nodes[node_id] = node

        if parent_id and parent_id in self._nodes:
            self._nodes[parent_id].children.append(node_id)
        else:
            self._roots.append(node_id)

        self._save()
        return node_id

    def update_result(
        self,
        node_id: str,
        status: str,
        metrics: dict,
        failure_reason: str = "",
        key_finding: str = "",
        hypothesis_verdict: str = "",
    ):
        """Update a node after experiment execution."""
        if node_id not in self._nodes:
            return
        n = self._nodes[node_id]
        n.status = status
        n.metrics = metrics
        n.failure_reason = failure_reason
        n.key_finding = key_finding
        n.hypothesis_verdict = hypothesis_verdict
        self._save()

    def spawn_child(
        self,
        parent_node_id: str,
        experiment_id: str,
        title: str,
        hypothesis: str,
        source: str = "loop",
    ) -> str:
        """Create a child experiment from a parent's results (autonomous loop)."""
        parent = self._nodes.get(parent_node_id)
        depth = (parent.depth + 1) if parent else 1
        domain = parent.domain if parent else ""
        return self.add_experiment(
            experiment_id=experiment_id,
            title=title,
            hypothesis=hypothesis,
            domain=domain,
            parent_id=parent_node_id,
            source=source,
            depth=depth,
        )

    # ── Query ────────────────────────────────────────────────────────────────

    def get_research_tree(self, domain: str = "") -> Dict:
        """
        Return the full research tree as a nested dict for visualisation.
        Suitable for D3.js tree layout or Plotly treemap.
        """
        def node_to_nested(node_id: str) -> dict:
            if node_id not in self._nodes:
                return {}
            n = self._nodes[node_id]
            status_color = {
                "success": "#22c55e",
                "failed": "#ef4444",
                "inconclusive": "#f59e0b",
                "designed": "#3b82f6",
                "running": "#a855f7",
            }.get(n.status, "#6b7280")
            return {
                "id": n.node_id,
                "name": n.title[:50],
                "status": n.status,
                "color": status_color,
                "depth": n.depth,
                "source": n.source,
                "scientist_score": n.scientist_score,
                "key_finding": n.key_finding[:100] if n.key_finding else "",
                "failure_reason": n.failure_reason[:100] if n.failure_reason else "",
                "metrics": n.metrics,
                "children": [node_to_nested(c) for c in n.children if c in self._nodes],
            }

        roots = self._roots
        if domain:
            roots = [r for r in roots
                     if self._nodes.get(r, ExperimentNode("","","","","","")).domain.lower()
                     == domain.lower()]

        return {
            "name": domain or "All Research",
            "children": [node_to_nested(r) for r in roots if r in self._nodes],
        }

    def get_flat_list(self, domain: str = "") -> List[dict]:
        """Return flat list of all nodes for table display."""
        nodes = list(self._nodes.values())
        if domain:
            nodes = [n for n in nodes if domain.lower() in n.domain.lower()]
        nodes.sort(key=lambda x: x.created_at, reverse=True)
        return [n.to_dict() for n in nodes]

    def get_failure_patterns(self) -> List[dict]:
        """Detect common failure patterns across all experiments."""
        failed = [n for n in self._nodes.values() if n.status == "failed"]
        if not failed:
            return []

        # Group by failure reason keywords
        patterns: dict = {}
        for n in failed:
            reason = n.failure_reason.lower()
            key = "overfitting" if "overfit" in reason else \
                  "underfitting" if "underfit" in reason or "too simple" in reason else \
                  "data_issue" if "data" in reason or "dataset" in reason else \
                  "compute" if "timeout" in reason or "memory" in reason else \
                  "other"
            if key not in patterns:
                patterns[key] = {"pattern": key, "count": 0, "examples": []}
            patterns[key]["count"] += 1
            patterns[key]["examples"].append(n.title[:60])

        return sorted(patterns.values(), key=lambda x: -x["count"])

    def get_success_patterns(self) -> List[dict]:
        """Extract patterns from successful experiments."""
        successful = [n for n in self._nodes.values()
                      if n.status == "success" and n.key_finding]
        return [
            {"title": n.title, "key_finding": n.key_finding,
             "scientist_score": n.scientist_score, "source": n.source,
             "metrics": n.metrics}
            for n in successful
        ]

    def get_stats(self) -> Dict:
        nodes = list(self._nodes.values())
        if not nodes:
            return {"total": 0}
        return {
            "total": len(nodes),
            "by_status": {
                "designed": sum(1 for n in nodes if n.status == "designed"),
                "success": sum(1 for n in nodes if n.status == "success"),
                "failed": sum(1 for n in nodes if n.status == "failed"),
                "inconclusive": sum(1 for n in nodes if n.status == "inconclusive"),
            },
            "by_source": {
                "standard": sum(1 for n in nodes if n.source == "standard"),
                "cross_paper": sum(1 for n in nodes if n.source == "cross_paper_synthesis"),
                "loop": sum(1 for n in nodes if n.source == "loop"),
                "twin": sum(1 for n in nodes if n.source == "twin"),
            },
            "max_depth": max(n.depth for n in nodes),
            "avg_scientist_score": round(
                sum(n.scientist_score for n in nodes) / len(nodes), 2),
        }

    # ── Persistence ──────────────────────────────────────────────────────────

    def _save(self):
        data = {
            "nodes": {k: v.to_dict() for k, v in self._nodes.items()},
            "roots": self._roots,
        }
        self._path.write_text(json.dumps(data, indent=2))

    def _load(self):
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            for k, v in data.get("nodes", {}).items():
                self._nodes[k] = ExperimentNode(**v)
            self._roots = data.get("roots", [])
            logger.info(f"[Warehouse] Loaded {len(self._nodes)} experiment nodes")
        except Exception as exc:
            logger.warning(f"[Warehouse] Load failed: {exc}")
