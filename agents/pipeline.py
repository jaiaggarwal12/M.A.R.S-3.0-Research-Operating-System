"""
M.A.R.S 4.0 — Research Operating System Pipeline
15-node LangGraph with Arena, Cross-Paper, Warehouse, Specialist Panel
"""
from __future__ import annotations
import time
from langgraph.graph import StateGraph, END
from core.state import MARSState
from core.logger import logger
from core import metrics, config

from services.ingestion.arxiv_client import ArxivClient
from services.ingestion.vector_store import VectorStore
from services.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from services.memory.research_memory import ResearchMemory
from services.specialist_debate.specialist_panel import SpecialistPanel
from services.hypothesis.hypothesis_generator import HypothesisGenerator
from services.cross_paper.cross_paper_reasoner import CrossPaperReasoner
from services.arena.benchmark_arena import BenchmarkArena
from services.experiment.experiment_designer import ExperimentDesigner
from services.runner.experiment_runner import ExperimentRunner
from services.analyzer.result_analyzer import ResultAnalyzer
from services.report.report_generator import ReportGenerator
from services.twin.research_twin import ResearchTwin
from services.warehouse.experiment_warehouse import ExperimentWarehouse

from agents.nodes import (
    make_ingest_node, make_graph_node, make_memory_node,
    make_literature_node, make_cross_paper_node, make_hypothesis_node,
    make_arena_node, make_panel_node, make_design_node,
    make_warehouse_register_node, make_run_node, make_analyze_node,
    make_twin_node, make_loop_controller, make_report_node,
)


class MARSPipeline:
    """
    M.A.R.S 4.0 — Research Operating System
    15-node autonomous research pipeline.
    """

    def __init__(self):
        self.arxiv        = ArxivClient()
        self.vector_store = VectorStore()
        self.kg           = KnowledgeGraphBuilder()
        self.memory       = ResearchMemory()
        self.panel        = SpecialistPanel()
        self.hyp_gen      = HypothesisGenerator(self.kg)
        self.reasoner     = CrossPaperReasoner()
        self.arena        = BenchmarkArena()
        self.designer     = ExperimentDesigner()
        self.runner       = ExperimentRunner()
        self.analyzer     = ResultAnalyzer()
        self.report_gen   = ReportGenerator()
        self.twin         = ResearchTwin()
        self.warehouse    = ExperimentWarehouse()
        self._twin_persona = "Andrej Karpathy"
        self.graph        = self._build()
        logger.info("M.A.R.S 4.0 Research Operating System ready")

    def run(self, query: str, domain: str = "", run_experiments: bool = True,
            twin_persona: str = "Andrej Karpathy") -> MARSState:
        self._twin_persona = twin_persona
        t0 = time.perf_counter()
        logger.info(f"[Pipeline] '{query}'")

        initial: MARSState = {
            "query": query, "domain": domain or query,
            "loop_iteration": 0, "loop_history": [], "loop_should_continue": False,
            "stage": "start", "run_experiments": run_experiments,
            "papers": [], "search_queries": [], "papers_count": 0,
            "graph_stats": {}, "citation_network": {}, "research_clusters": [],
            "influential_papers": [], "_graph_gaps": [],
            "vector_results": [], "retrieval_mode": "hybrid",
            "literature_summary": "", "key_papers": [],
            "paper_components": {}, "cross_paper_combinations": [], "component_matrix": {},
            "memory_context": [], "raw_hypotheses": [], "hypotheses": [],
            "arena_ranked": [], "top_portfolio": [], "arena_stats": {},
            "research_gaps": [], "trending_topics": [], "trends": {},
            "debate_transcript": "", "sota_benchmarks": {},
            "experiment_plans": [], "warehouse_node_ids": {},
            "experiment_results": [], "execution_errors": [], "analysis": {},
            "twin_persona": twin_persona, "twin_hypothesis": "",
            "final_report": "", "report_path": "",
        }

        result = self.graph.invoke(initial)
        elapsed = round(time.perf_counter() - t0, 2)
        result["latency_sec"] = elapsed
        metrics.record_latency(elapsed)
        metrics.inc("queries_answered")
        logger.info(f"[Pipeline] Done in {elapsed}s")
        return result

    def _build(self):
        builder = StateGraph(MARSState)
        tp = self._twin_persona

        builder.add_node("ingest",      make_ingest_node(self.arxiv, self.vector_store))
        builder.add_node("build_graph", make_graph_node(self.kg))
        builder.add_node("memory",      make_memory_node(self.memory))
        builder.add_node("literature",  make_literature_node(self.vector_store, self.kg))
        builder.add_node("cross_paper", make_cross_paper_node(self.reasoner))
        builder.add_node("hypothesize", make_hypothesis_node(self.hyp_gen, self.reasoner))
        builder.add_node("arena",       make_arena_node(self.arena))
        builder.add_node("panel",       make_panel_node(self.panel, self.memory))
        builder.add_node("design",      make_design_node(self.designer))
        builder.add_node("warehouse",   make_warehouse_register_node(self.warehouse))
        builder.add_node("run",         make_run_node(self.runner))
        builder.add_node("analyze",     make_analyze_node(self.analyzer, self.memory, self.warehouse))
        builder.add_node("twin",        make_twin_node(self.twin, tp))
        builder.add_node("loop_ctrl",   make_loop_controller(self.memory))
        builder.add_node("report",      make_report_node(self.report_gen))

        builder.set_entry_point("ingest")
        for a, b in [
            ("ingest","build_graph"), ("build_graph","memory"), ("memory","literature"),
            ("literature","cross_paper"), ("cross_paper","hypothesize"),
            ("hypothesize","arena"), ("arena","panel"), ("panel","design"),
            ("design","warehouse"), ("warehouse","run"), ("run","analyze"),
            ("analyze","twin"), ("twin","loop_ctrl"),
        ]:
            builder.add_edge(a, b)

        builder.add_conditional_edges(
            "loop_ctrl",
            lambda s: "ingest" if s.get("loop_should_continue") else "report",
            {"ingest": "ingest", "report": "report"},
        )
        builder.add_edge("report", END)
        return builder.compile()

    def close(self):
        self.kg.close()
