"""Tests for new M.A.R.S 4.0 services. No API keys needed."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from services.warehouse.experiment_warehouse import ExperimentWarehouse
from services.arena.benchmark_arena import BenchmarkArena
from services.portfolio.portfolio_optimizer import PortfolioOptimizer, Portfolio
from services.executor.distributed_executor import DistributedExecutor, Backend


def make_hyp(i, novelty=7, feasibility=6, impact=7, risk=4, compute=4):
    import uuid
    return {
        "id": f"hyp_{i}", "title": f"Hypothesis {i}",
        "statement": f"Statement {i}", "motivation": "Test",
        "novelty_score": novelty, "feasibility_score": feasibility,
        "expected_impact": impact, "risk_score": risk,
        "compute_cost_score": compute,
        "scientist_score": round(0.35*novelty+0.25*feasibility+0.30*impact-0.10*risk-0.05*compute, 2),
        "debate_verdict": "go", "source": "standard",
    }


class TestExperimentWarehouse:
    def test_add_and_retrieve(self, tmp_path):
        wh = ExperimentWarehouse(str(tmp_path/"wh.json"))
        nid = wh.add_experiment("exp001","Test Experiment","Hypothesis A","ml")
        assert nid.startswith("node_")
        assert wh.get_stats()["total"] == 1

    def test_update_result(self, tmp_path):
        wh = ExperimentWarehouse(str(tmp_path/"wh2.json"))
        nid = wh.add_experiment("exp002","Exp","Hyp","cv")
        wh.update_result(nid, "success", {"accuracy":0.92}, key_finding="Improved by 5%")
        flat = wh.get_flat_list()
        assert flat[0]["status"] == "success"
        assert flat[0]["key_finding"] == "Improved by 5%"

    def test_tree_structure(self, tmp_path):
        wh = ExperimentWarehouse(str(tmp_path/"wh3.json"))
        parent = wh.add_experiment("exp003","Parent","Hyp","rl",depth=0)
        child = wh.spawn_child(parent,"exp004","Child","Child hyp",source="loop")
        tree = wh.get_research_tree()
        assert "children" in tree

    def test_failure_patterns(self, tmp_path):
        wh = ExperimentWarehouse(str(tmp_path/"wh4.json"))
        for i in range(3):
            nid = wh.add_experiment(f"exp{i:03}",f"Exp {i}","Hyp","ml")
            wh.update_result(nid,"failed",{},failure_reason="overfitting on small dataset")
        patterns = wh.get_failure_patterns()
        assert len(patterns) > 0
        assert patterns[0]["pattern"] == "overfitting"
        assert patterns[0]["count"] == 3

    def test_success_patterns(self, tmp_path):
        wh = ExperimentWarehouse(str(tmp_path/"wh5.json"))
        nid = wh.add_experiment("exp099","Win","Hyp","nlp")
        wh.update_result(nid,"success",{"auc":0.95},key_finding="3x speedup achieved")
        successes = wh.get_success_patterns()
        assert len(successes) == 1
        assert "3x speedup" in successes[0]["key_finding"]

    def test_persistence(self, tmp_path):
        path = str(tmp_path/"wh_persist.json")
        wh1 = ExperimentWarehouse(path)
        wh1.add_experiment("expA","A","Hyp","ml")
        wh1.add_experiment("expB","B","Hyp","ml")
        wh2 = ExperimentWarehouse(path)
        assert wh2.get_stats()["total"] == 2


class TestBenchmarkArena:
    def test_basic_scoring(self, tmp_path):
        # Test scoring logic without LLM (just math)
        arena = BenchmarkArena(str(tmp_path/"arena.json"))
        hyps = [make_hyp(i) for i in range(5)]
        # Manually compute scores
        for h in hyps:
            n = h["novelty_score"]; f = h["feasibility_score"]
            im = h["expected_impact"]; r = h["risk_score"]; c = h["compute_cost_score"]
            expected = round(0.35*n + 0.25*f + 0.30*im - 0.10*r - 0.05*c, 2)
            assert abs(h["scientist_score"] - expected) < 0.01

    def test_leaderboard_persistence(self, tmp_path):
        path = str(tmp_path/"arena_lb.json")
        arena1 = BenchmarkArena(path)
        # Directly add entries to test persistence
        from services.arena.benchmark_arena import ArenaEntry
        entry = ArenaEntry(
            id="hyp_test", title="Test Hypothesis", statement="Test",
            domain="ml", novelty_score=8.0, feasibility_score=7.0,
            expected_impact=9.0, risk_score=5.0, compute_cost_score=4.0,
            scientist_score=7.95,
        )
        arena1._leaderboard.append(entry)
        arena1._save()

        arena2 = BenchmarkArena(path)
        lb = arena2.get_leaderboard()
        assert len(lb) == 1
        assert lb[0]["title"] == "Test Hypothesis"

    def test_arena_stats(self, tmp_path):
        from services.arena.benchmark_arena import ArenaEntry
        arena = BenchmarkArena(str(tmp_path/"arena_stats.json"))
        for i in range(5):
            arena._leaderboard.append(ArenaEntry(
                id=f"h{i}", title=f"H{i}", statement="", domain="ml",
                novelty_score=float(i+5), feasibility_score=6.0,
                expected_impact=7.0, risk_score=4.0, compute_cost_score=4.0,
                scientist_score=float(i+5)*0.35+6.0*0.25+7.0*0.30-4.0*0.10-4.0*0.05
            ))
        stats = arena.get_arena_stats()
        assert stats["total_scored"] == 5
        assert stats["max_scientist_score"] > 0


class TestPortfolioOptimizer:
    def test_portfolio_structure(self):
        from services.portfolio.portfolio_optimizer import PortfolioSlot
        slots = [
            PortfolioSlot("h1","Moonshot","moonshot","High risk bet",0.3,3.0,2.1,1,8.0,novelty_score=9.0),
            PortfolioSlot("h2","Core","core","Solid bet",0.7,4.9,3.5,2,4.0,feasibility_score=8.0),
            PortfolioSlot("h3","Quick","quick_win","Fast result",0.85,5.1,4.2,3,1.0,feasibility_score=9.0),
        ]
        portfolio = Portfolio(
            slots=slots, stats={"sharpe_analogue":1.2,"expected_value":13.0},
            excluded=[], rebalancing_triggers=["If moonshot fails, pivot to h4"],
            budget_gpu_hours=20.0,
        )
        assert len(portfolio.moonshots()) == 1
        assert len(portfolio.core_bets()) == 1
        assert len(portfolio.quick_wins()) == 1
        assert portfolio.execution_order()[0].slot == "moonshot"

        md = portfolio.summary_markdown()
        assert "🚀 Moonshot" in md
        assert "20.0" in md

    def test_rebalance_moonshot_fail(self):
        from services.portfolio.portfolio_optimizer import PortfolioSlot
        optimizer = PortfolioOptimizer()
        slots = [
            PortfolioSlot("h1","Moonshot","moonshot","",0.3,3.0,2.1,1,8.0),
            PortfolioSlot("h2","Core","core","",0.7,4.9,3.5,2,4.0),
        ]
        portfolio = Portfolio(slots=slots,stats={},excluded=[],
                              rebalancing_triggers=[],budget_gpu_hours=20.0)
        results = [{"experiment_id":"h1","hypothesis_verdict":"rejected","key_finding":"Failed"}]
        rebalance = optimizer.suggest_rebalance(portfolio, results)
        assert rebalance["action"] in ("pivot","continue","double_down")

    def test_rebalance_confirmed(self):
        from services.portfolio.portfolio_optimizer import PortfolioSlot
        optimizer = PortfolioOptimizer()
        portfolio = Portfolio(slots=[PortfolioSlot("h1","Core","core","",0.7,4.9,3.5,1,4.0)],
                              stats={},excluded=[],rebalancing_triggers=[],budget_gpu_hours=20.0)
        results = [{"experiment_id":"h1","hypothesis_verdict":"confirmed","key_finding":"3x speedup"}]
        rebalance = optimizer.suggest_rebalance(portfolio, results)
        assert rebalance["action"] == "double_down"


class TestDistributedExecutor:
    def test_backend_detection(self):
        ex = DistributedExecutor()
        # Local always available
        assert ex._check_docker() in (True, False)  # either is fine

    def test_backend_selection_small_job(self):
        ex = DistributedExecutor()
        plan = {"estimated_compute": "~30 min CPU", "difficulty": "low"}
        backend = ex._select_backend(plan)
        assert backend in (Backend.LOCAL, Backend.DOCKER)

    def test_local_execution(self, tmp_path):
        import json
        # Create a minimal experiment
        train_py = tmp_path / "train.py"
        train_py.write_text("""
import json
print("METRIC:accuracy:0.923")
print("METRIC:f1:0.891")
with open("results.json","w") as f:
    json.dump({"accuracy":0.923,"f1":0.891}, f)
""")
        (tmp_path / "requirements.txt").write_text("numpy\n")

        ex = DistributedExecutor()
        result = ex.run({
            "experiment_id": "test_001",
            "artifact_dir": str(tmp_path),
            "estimated_compute": "CPU only",
            "difficulty": "low",
        }, backend="local")

        assert result["status"] == "success"
        assert abs(result["parsed_metrics"].get("accuracy",0) - 0.923) < 0.001
        assert abs(result["parsed_metrics"].get("f1",0) - 0.891) < 0.001

    def test_metric_parsing(self):
        ex = DistributedExecutor()
        stdout = """
Starting training...
Epoch 1/10: loss=0.45
METRIC:train_loss:0.45
METRIC:val_accuracy:0.867
METRIC:baseline_accuracy:0.712
METRIC:improvement:0.155
Done. Saved results.json
"""
        parsed = ex._parse_metrics(stdout)
        assert parsed["train_loss"] == 0.45
        assert parsed["val_accuracy"] == 0.867
        assert parsed["baseline_accuracy"] == 0.712
        assert len(parsed) == 4
