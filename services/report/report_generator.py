from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from core.logger import logger
from core import config, metrics


class ReportGenerator:
    def __init__(self):
        self.reports_dir = Path(config.DATA_DIR) / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, state: dict) -> dict:
        query = state.get("query","Research Analysis")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        bench = metrics.snapshot()
        md = self._build(state, query, now, bench)
        slug = query.lower().replace(" ","_")[:40]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_path = self.reports_dir / f"report_{slug}_{ts}.md"
        md_path.write_text(md)
        logger.info(f"[Report] {md_path.name}")
        return {"final_report": md, "report_path": str(md_path)}

    def _build(self, s, query, now, bench) -> str:
        analysis = s.get("analysis",{}); analyses = analysis.get("analyses",[])
        stats = analysis.get("summary_stats",{}); gs = s.get("graph_stats",{})
        hypotheses = s.get("hypotheses",[]); arena_ranked = s.get("arena_ranked",[])
        arena_stats = s.get("arena_stats",{}); cp_combos = s.get("cross_paper_combinations",[])

        md = f"# M.A.R.S 4.0 Research Report\n## {query}\n*{now}*\n\n---\n\n"
        md += f"## Executive Summary\n{analysis.get('overall_insight','Analysis complete.')}\n\n---\n\n"
        md += f"## Live Benchmarks\n\n| Metric | Value |\n|--------|-------|\n"
        md += f"| Papers indexed | {bench['papers_indexed']:,} |\n"
        md += f"| Graph nodes | {gs.get('nodes',0):,} |\n"
        md += f"| Cross-paper combinations | {bench['cross_paper_combinations']} |\n"
        md += f"| Arena scored | {bench['arena_scored']} |\n"
        md += f"| Experiments run | {stats.get('total',0)} |\n"
        md += f"| Successful discoveries | {bench['successful_discoveries']} |\n"
        md += f"| Success rate | {bench['experiment_success_rate']}% |\n"
        md += f"| Avg latency | {bench['avg_latency_sec']}s |\n\n---\n\n"

        md += f"## Literature Review\n{s.get('literature_summary','N/A')}\n\n---\n\n"

        md += "## Research Gaps\n"
        for g in s.get("research_gaps",[])[:6]: md += f"- {g}\n"

        if cp_combos:
            md += "\n---\n\n## Cross-Paper Synthesis\n"
            for c in cp_combos[:4]:
                a = c.get("component_a",{}); b = c.get("component_b",{})
                md += (f"\n**{c.get('proposed_experiment_title','')}**\n"
                       f"- `{a.get('component_type','')}` from _{a.get('paper_title','')}_: `{a.get('component','')}`\n"
                       f"- `{b.get('component_type','')}` from _{b.get('paper_title','')}_: `{b.get('component','')}`\n"
                       f"Rationale: {c.get('combination_rationale','')}\n")

        if arena_ranked:
            md += "\n---\n\n## Arena Leaderboard\n\n"
            md += "| Rank | Title | Score | Novelty | Feasibility | Impact | Venue |\n"
            md += "|------|-------|-------|---------|-------------|--------|-------|\n"
            for h in arena_ranked[:10]:
                md += (f"| {h.get('rank','')} | {h.get('title','')[:45]} | "
                       f"**{h.get('scientist_score',0):.1f}** | {h.get('novelty_score',0)}/10 | "
                       f"{h.get('feasibility_score',0)}/10 | {h.get('expected_impact',0)}/10 | "
                       f"{h.get('estimated_venue', h.get('publishability','?'))} |\n")

        if hypotheses:
            md += "\n---\n\n## Specialist Panel Results\n"
            for h in hypotheses:
                ve = {"go":"✅","no-go":"❌","conditional":"⚠️"}.get(h.get("debate_verdict",""),"❓")
                md += (f"\n### {ve} {h.get('title','')}\n"
                       f"**Statement:** {h.get('statement','')}\n"
                       f"Scientist: {h.get('scientist_score','?')} | Reviewer: {h.get('reviewer_score','?')}/8 | "
                       f"Statistician: {h.get('statistician_verdict','?')} | Venue: {h.get('estimated_venue','?')}\n")
                if h.get("statistician_fixes"):
                    md += "**Statistician fixes required:**\n"
                    for f in h["statistician_fixes"]: md += f"- {f}\n"

        debate = s.get("debate_transcript","")
        if debate:
            md += f"\n---\n\n## Panel Transcripts\n<details><summary>Expand</summary>\n\n{debate[:4000]}\n\n</details>\n"

        if analyses:
            md += "\n---\n\n## Experiment Results\n"
            for a in analyses:
                ve = {"confirmed":"✅","rejected":"❌","partial":"⚠️"}.get(a.get("hypothesis_verdict",""),"❓")
                md += (f"\n### {a.get('title','')}\n"
                       f"**Verdict:** {ve} {a.get('hypothesis_verdict','').upper()}\n"
                       f"**Finding:** {a.get('key_finding','')}\n")
                if a.get("metrics"):
                    md += "**Metrics:** " + " | ".join(f"`{k}={v}`" for k,v in list(a["metrics"].items())[:5]) + "\n"
                if a.get("sota_comparisons"):
                    for c in a["sota_comparisons"]:
                        arrow = "↑" if c.get("status")=="above_sota" else "↓"
                        md += f"vs SOTA: `{c['metric']}={c['your_value']}` vs `{c['sota_value']}` {arrow}\n"

        if s.get("twin_hypothesis"):
            md += f"\n---\n\n## Research Twin ({s.get('twin_persona','')})\n{s['twin_hypothesis']}\n"

        md += "\n---\n*M.A.R.S 4.0 — Research Operating System*\n"
        return md

    def _json(self, s, query, now, bench): 
        return {"query":query,"generated_at":now,"benchmarks":bench,
                "arena_ranked":s.get("arena_ranked",[])[:10]}
