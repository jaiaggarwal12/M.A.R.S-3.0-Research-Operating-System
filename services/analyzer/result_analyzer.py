from __future__ import annotations
import json
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import get_llm
from core.logger import logger
from services.benchmark.sota_retriever import SOTARetriever

ANALYSIS_PROMPT = """You are an ML research analyst.
Given experiment results vs baselines, provide JSON:
{
  "interpretation": "2-3 sentences on what the results mean",
  "hypothesis_verdict": "confirmed|rejected|inconclusive|partial",
  "verdict_reasoning": "1-2 sentences",
  "key_finding": "single most important finding",
  "improvement_suggestions": ["suggestion1","suggestion2"],
  "paper_potential": "high|medium|low",
  "paper_reasoning": "1 sentence"
}
Return ONLY valid JSON."""


class ResultAnalyzer:
    def __init__(self):
        self._sota = SOTARetriever()

    def analyze(self, experiment_results, experiment_plans, hypotheses, domain="") -> Dict:
        logger.info(f"[Analyzer] {len(experiment_results)} results")
        plan_map = {p.get("experiment_id",""): p for p in experiment_plans}
        hyp_map  = {h.get("id",""): h for h in hypotheses}
        sota = self._sota.get_sota(domain) if domain else {}

        analyses, stats = [], {"total":0,"success":0,"failed":0,"confirmed":0,"rejected":0,"inconclusive":0}

        for result in experiment_results:
            stats["total"] += 1
            exp_id = result.get("experiment_id","")
            plan = plan_map.get(exp_id,{})
            hyp  = hyp_map.get(plan.get("hypothesis_id",""),{})

            if result.get("status") == "success":
                stats["success"] += 1
                a = self._analyze_one(result, plan, hyp, sota)
            else:
                stats["failed"] += 1
                a = {"experiment_id":exp_id,"title":result.get("title",exp_id),
                     "hypothesis_verdict":"inconclusive","verdict_reasoning":f"Experiment failed: {result.get('error','')[:200]}",
                     "key_finding":"Experiment did not complete","interpretation":"Fix errors and retry.",
                     "improvement_suggestions":["Fix runtime errors","Check dependencies"],
                     "paper_potential":"low","paper_reasoning":"Needs to run first","metrics":{}}

            v = a.get("hypothesis_verdict","inconclusive")
            stats["confirmed" if v=="confirmed" else "rejected" if v=="rejected" else "inconclusive"] += 1
            analyses.append(a)

        return {"analyses":analyses,"summary_stats":stats,"overall_insight":self._overall(analyses,stats)}

    def _analyze_one(self, result, plan, hyp, sota) -> dict:
        m = {**result.get("parsed_metrics",{}), **result.get("results_json",{})}

        # SOTA comparison
        sota_comparisons = []
        for metric_name, val in m.items():
            if isinstance(val, (int,float)):
                comp = self._sota.compare_to_sota(metric_name, val, sota)
                if comp.get("sota_value"):
                    sota_comparisons.append(comp)

        context = (
            f"Experiment: {plan.get('title','')}\n"
            f"Hypothesis: {hyp.get('statement', plan.get('hypothesis',''))}\n"
            f"Metrics: {json.dumps(m, indent=2)}\n"
            f"Baselines: {', '.join(plan.get('baselines',[]))}\n"
            f"SOTA comparisons: {json.dumps(sota_comparisons, indent=2)}\n"
            f"Stdout (last 500): {result.get('stdout','')[-500:]}"
        )

        llm = get_llm(temperature=0.1)
        resp = llm.invoke([SystemMessage(content=ANALYSIS_PROMPT), HumanMessage(content=context)])
        parsed = self._parse(resp.content)
        parsed["experiment_id"] = result.get("experiment_id","")
        parsed["title"] = plan.get("title",result.get("experiment_id",""))
        parsed["metrics"] = m
        parsed["sota_comparisons"] = sota_comparisons
        return parsed

    def _overall(self, analyses, stats) -> str:
        if not analyses: return "No experiments."
        confirmed = [a for a in analyses if a.get("hypothesis_verdict")=="confirmed"]
        lines = [f"Ran {stats['total']} experiments: {stats['success']} succeeded.",
                 f"{stats['confirmed']} confirmed, {stats['rejected']} rejected, {stats['inconclusive']} inconclusive."]
        if confirmed: lines.append(f"Most promising: {confirmed[0].get('title','')}")
        paper_high = [a for a in analyses if a.get("paper_potential")=="high"]
        if paper_high: lines.append(f"Publication potential: {paper_high[0].get('title','')} — {paper_high[0].get('paper_reasoning','')}")
        return " ".join(lines)

    @staticmethod
    def _parse(raw) -> dict:
        raw = raw.strip()
        if "```" in raw:
            for p in raw.split("```"):
                p = p.strip().lstrip("json").strip()
                if p.startswith("{"): raw = p; break
        try: return json.loads(raw)
        except: return {"interpretation":raw[:300],"hypothesis_verdict":"inconclusive",
                        "verdict_reasoning":"Parse failed","key_finding":"","improvement_suggestions":[],
                        "paper_potential":"low","paper_reasoning":""}
