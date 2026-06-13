"""M.A.R.S 4.0 State"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, TypedDict

class MARSState(TypedDict, total=False):
    query: str
    domain: str
    loop_iteration: int
    papers: List[Dict]
    search_queries: List[str]
    papers_count: int
    graph_stats: Dict
    citation_network: Dict
    research_clusters: List[Dict]
    influential_papers: List[Dict]
    _graph_gaps: List[Dict]
    vector_results: List[Dict]
    graph_results: List[Dict]
    retrieval_mode: str
    literature_summary: str
    key_papers: List[Dict]
    paper_components: Dict
    cross_paper_combinations: List[Dict]
    component_matrix: Dict
    memory_context: List[Dict]
    raw_hypotheses: List[Dict]
    arena_ranked: List[Dict]
    top_portfolio: List[Dict]
    arena_stats: Dict
    debate_transcript: str
    hypotheses: List[Dict]
    research_gaps: List[str]
    trending_topics: List[str]
    trends: Dict
    sota_benchmarks: Dict
    experiment_plans: List[Dict]
    warehouse_node_ids: Dict
    experiment_results: List[Dict]
    execution_errors: List[str]
    analysis: Dict
    twin_persona: str
    twin_hypothesis: str
    loop_should_continue: bool
    loop_history: List[Dict]
    final_report: str
    report_path: str
    stage: str
    run_experiments: bool
    error: Optional[str]
    latency_sec: float
