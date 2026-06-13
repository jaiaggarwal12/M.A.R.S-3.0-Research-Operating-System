"""Live benchmark tracker."""
from __future__ import annotations
import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_counters: dict = defaultdict(float)
_latencies: list = []
_exp_total = 0
_exp_success = 0

def inc(key: str, n: float = 1.0):
    with _lock: _counters[key] += n

def record_latency(s: float):
    with _lock:
        _latencies.append(s)
        if len(_latencies) > 1000: _latencies.pop(0)

def record_experiment(success: bool):
    global _exp_total, _exp_success
    with _lock:
        _exp_total += 1
        if success: _exp_success += 1

def snapshot() -> dict:
    with _lock:
        avg = round(sum(_latencies)/len(_latencies),2) if _latencies else 0.0
        rate = round(_exp_success/_exp_total*100,1) if _exp_total > 0 else 0.0
        return {
            "papers_indexed":           int(_counters["papers_indexed"]),
            "graph_nodes":              int(_counters["graph_nodes"]),
            "graph_edges":              int(_counters["graph_edges"]),
            "queries_answered":         int(_counters["queries_answered"]),
            "hypotheses_generated":     int(_counters["hypotheses_generated"]),
            "cross_paper_combinations": int(_counters["cross_paper_combinations"]),
            "arena_scored":             int(_counters["arena_scored"]),
            "experiments_designed":     int(_counters["experiments_designed"]),
            "experiments_run":          _exp_total,
            "successful_discoveries":   int(_counters["successful_discoveries"]),
            "novel_gaps_found":         int(_counters["novel_gaps_found"]),
            "debate_rounds":            int(_counters["debate_rounds"]),
            "memory_entries":           int(_counters["memory_entries"]),
            "experiment_success_rate":  rate,
            "avg_latency_sec":          avg,
        }

class Timer:
    def __init__(self): self._s = 0.0
    def __enter__(self): self._s = time.perf_counter(); return self
    def __exit__(self, *_): record_latency(time.perf_counter() - self._s)
