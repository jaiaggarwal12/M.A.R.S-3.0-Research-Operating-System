"""
M.A.R.S 3.0 test suite — no API keys or Neo4j needed.
pytest tests/ -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from services.ingestion.arxiv_client import PaperRecord
from services.ingestion.vector_store import VectorStore
from services.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from services.memory.research_memory import ResearchMemory
from services.debate.multi_agent_debate import MultiAgentDebate
from services.benchmark.sota_retriever import SOTARetriever
from services.twin.research_twin import ResearchTwin
from core.metrics import snapshot, inc, record_experiment


def paper(i, cats=None):
    return PaperRecord(
        arxiv_id=f"2401.{i:05d}", title=f"Paper {i}: LLM Inference Optimization",
        authors=[f"Author {i}"], abstract=f"Method {i} for speculative decoding and KV-cache.",
        published="2024-03-15T00:00:00+00:00", updated="2024-03-15T00:00:00+00:00",
        categories=cats or ["cs.LG","cs.CL"], pdf_url=f"https://arxiv.org/pdf/2401.{i:05d}",
        entry_url=f"https://arxiv.org/abs/2401.{i:05d}", citation_count=i*10)


# ── VectorStore ──────────────────────────────────────────────────────────────

class TestVectorStore:
    def test_add_search(self, tmp_path):
        vs = VectorStore(str(tmp_path/"idx"))
        added = vs.add_papers([paper(i) for i in range(5)])
        assert added == 5
        results = vs.search("speculative decoding", k=3)
        assert len(results) > 0
        assert "title" in results[0][0]

    def test_dedup(self, tmp_path):
        vs = VectorStore(str(tmp_path/"idx2"))
        vs.add_papers([paper(1)])
        assert vs.add_papers([paper(1)]) == 0


# ── KnowledgeGraph ───────────────────────────────────────────────────────────

class TestKnowledgeGraph:
    def test_ingest_and_pagerank(self):
        kg = KnowledgeGraphBuilder()
        kg.ingest_papers([paper(i) for i in range(6)])
        influential = kg.get_influential_papers(3)
        assert len(influential) <= 3

    def test_gap_detection(self):
        kg = KnowledgeGraphBuilder()
        papers = [paper(i, cats=["cs.LG"] if i%2==0 else ["cs.CV"]) for i in range(12)]
        kg.ingest_papers(papers)
        gaps = kg.detect_gaps()
        assert isinstance(gaps, list)

    def test_cluster_detection(self):
        kg = KnowledgeGraphBuilder()
        kg.ingest_papers([paper(i) for i in range(8)])
        clusters = kg.detect_research_clusters(min_size=2)
        assert isinstance(clusters, list)

    def test_citation_network_json(self):
        kg = KnowledgeGraphBuilder()
        kg.ingest_papers([paper(i) for i in range(5)])
        net = kg.get_citation_network_json(10)
        assert "nodes" in net and "edges" in net


# ── Research Memory ──────────────────────────────────────────────────────────

class TestResearchMemory:
    def test_add_and_query(self, tmp_path):
        mem = ResearchMemory(str(tmp_path/"mem.json"))
        hid = mem.add_hypothesis("Use MoE for feed ranking", "recommendation")
        assert hid.startswith("hyp_")
        assert mem.total() == 1

    def test_update_result(self, tmp_path):
        mem = ResearchMemory(str(tmp_path/"mem2.json"))
        hid = mem.add_hypothesis("Use GNNs for molecular property prediction", "chemistry")
        mem.update_result(hid, "failed", "−1.2% AUC", failure_reason="Overfitting",
                          metrics_dict={"auc": 0.812})
        failed = mem.get_failed_hypotheses()
        assert len(failed) == 1
        assert failed[0]["failure_reason"] == "Overfitting"

    def test_memory_context_format(self, tmp_path):
        mem = ResearchMemory(str(tmp_path/"mem3.json"))
        hid = mem.add_hypothesis("Hypothesis A", "ml")
        mem.update_result(hid, "success", "Improved accuracy by 5%")
        entries = mem.get_relevant_memory("ml", "hypothesis")
        ctx = mem.format_memory_context(entries)
        assert "RESEARCH MEMORY" in ctx


# ── SOTA Retriever ───────────────────────────────────────────────────────────

class TestSOTARetriever:
    def test_domain_fallback(self):
        r = SOTARetriever()
        sota = r.get_sota("LLM inference optimization")
        assert "tasks" in sota
        assert len(sota["tasks"]) > 0

    def test_compare_to_sota(self):
        r = SOTARetriever()
        sota = r.get_sota("LLM inference optimization")
        comp = r.compare_to_sota("tokens_per_second", 900.0, sota)
        assert "your_value" in comp
        assert comp["your_value"] == 900.0


# ── Research Twin ─────────────────────────────────────────────────────────────

class TestResearchTwin:
    def test_load_famous_persona(self, tmp_path):
        twin = ResearchTwin(str(tmp_path))
        persona = twin.load_famous_persona("Andrej Karpathy")
        assert persona["name"] == "Andrej Karpathy"
        assert len(persona["core_themes"]) > 0

    def test_list_personas(self, tmp_path):
        twin = ResearchTwin(str(tmp_path))
        twin.load_famous_persona("Andrew Ng")
        twin.load_famous_persona("Yann LeCun")
        assert "Andrew Ng" in twin.list_personas()
        assert "Yann LeCun" in twin.list_personas()


# ── Metrics ──────────────────────────────────────────────────────────────────

class TestMetrics:
    def test_snapshot_keys(self):
        snap = snapshot()
        for key in ["papers_indexed","graph_nodes","hypotheses_generated",
                     "experiments_run","successful_discoveries","novel_gaps_found"]:
            assert key in snap

    def test_record_experiment(self):
        record_experiment(True)
        record_experiment(False)
        snap = snapshot()
        assert snap["experiments_run"] >= 2

    def test_timer(self):
        from core.metrics import Timer
        import time
        with Timer():
            time.sleep(0.01)
        assert snapshot()["avg_latency_sec"] > 0
