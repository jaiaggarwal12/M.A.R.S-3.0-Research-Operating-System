"""M.A.R.S 4.0 — 8-tab Research OS Dashboard"""
from __future__ import annotations
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gradio as gr
import plotly.graph_objects as go
from agents.pipeline import MARSPipeline
from core.logger import logger
from core import metrics, config

_pipeline = None
def get_p():
    global _pipeline
    if _pipeline is None: _pipeline = MARSPipeline()
    return _pipeline

def run_full(query, run_exps, twin, progress=gr.Progress()):
    if not query.strip():
        return ("❌ Please enter a research query.","","","","","","","❌ Please enter a research query.")
    try:
        progress(0.05, desc="🔬 Initializing pipeline...")
        p = get_p()
        progress(0.15, desc="📡 Fetching papers from arxiv (takes 2-3 min)...")
        result = p.run(query, run_experiments=run_exps, twin_persona=twin)
        progress(1.0, desc="✅ Done!")
        bench = metrics.snapshot()
        report = result.get("final_report","")
        gaps_md = "\n".join(f"- {g}" for g in result.get("research_gaps",[])) or "None found"

        arena_md = ""
        for h in result.get("arena_ranked",[])[:8]:
            src = "🔗" if h.get("source")=="cross_paper_synthesis" else "📄"
            arena_md += (f"{src} **#{h.get('rank','')} {h.get('title','')[:50]}** "
                        f"— Score: **{h.get('scientist_score',0):.1f}** "
                        f"| N:{h.get('novelty_score',0)}/10 F:{h.get('feasibility_score',0)}/10 I:{h.get('expected_impact',0)}/10\n"
                        f"  _{h.get('one_line_pitch','')}_\n\n")

        cp_md = ""
        for c in result.get("cross_paper_combinations",[])[:3]:
            a = c.get("component_a",{}); b = c.get("component_b",{})
            cp_md += (f"**{c.get('proposed_experiment_title','')}**\n"
                     f"`{a.get('component_type','')}` from _{a.get('paper_title','')}_: `{a.get('component','')}`\n"
                     f"+ `{b.get('component_type','')}` from _{b.get('paper_title','')}_: `{b.get('component','')}`\n"
                     f"Rationale: {c.get('combination_rationale','')}\n\n")

        exp_md = ""
        for a in result.get("analysis",{}).get("analyses",[]):
            ve = {"confirmed":"✅","rejected":"❌","partial":"⚠️"}.get(a.get("hypothesis_verdict",""),"❓")
            exp_md += f"{ve} **{a.get('title','')}** — {a.get('key_finding','')}\n\n"

        bench_md = "| Metric | Value |\n|--------|-------|\n" + "\n".join(
            f"| {k.replace('_',' ').title()} | {v} |" for k,v in bench.items())

        papers_n = result.get("papers_count", 0)
        latency  = result.get("latency_sec", 0)
        status = f"✅ Done! Processed {papers_n} papers in {latency}s"
        return report, gaps_md, arena_md or "No hypotheses yet", cp_md or "No cross-paper combinations", exp_md or "No experiments run", bench_md, "", status
    except Exception as exc:
        logger.exception(str(exc))
        err = f"❌ Error: {exc}"
        return err,"","","","","","",err

def get_graph_viz():
    try:
        p = get_p()
        data = p.kg.get_citation_network_json(max_nodes=100)
        nodes = data.get("nodes",[]); edges = data.get("edges",[])
        if not nodes:
            fig = go.Figure(); fig.add_annotation(text="Run a query first", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False); return fig
        import networkx as nx
        G = nx.DiGraph()
        for n in nodes: G.add_node(n["id"],**n)
        nids = {n["id"] for n in nodes}
        for e in edges:
            if e["source"] in nids and e["target"] in nids: G.add_edge(e["source"],e["target"])
        pos = nx.spring_layout(G, k=1.2, seed=42)
        ex,ey=[],[]
        for u,v in G.edges(): ex+=[pos[u][0],pos[v][0],None]; ey+=[pos[u][1],pos[v][1],None]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ex,y=ey,mode="lines",line=dict(width=0.4,color="#555"),hoverinfo="none"))
        fig.add_trace(go.Scatter(
            x=[pos[n][0] for n in G.nodes()], y=[pos[n][1] for n in G.nodes()],
            mode="markers+text", text=[G.nodes[n].get("title","")[:30] for n in G.nodes()],
            textposition="top center", textfont=dict(size=7),
            marker=dict(size=[max(8,min(28,G.nodes[n].get("citations",0)//5+8)) for n in G.nodes()],
                color=[int(G.nodes[n].get("year","2020") or 2020) for n in G.nodes()],
                colorscale="Viridis",showscale=True,line=dict(width=0.5,color="#fff")),
            hovertext=[f"{G.nodes[n].get('title','')}<br>Year: {G.nodes[n].get('year','')} | Citations: {G.nodes[n].get('citations',0)}" for n in G.nodes()],
            hoverinfo="text"))
        fig.update_layout(showlegend=False,margin=dict(l=0,r=0,t=30,b=0),
            plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)",
            title="Citation Network (size=citations, color=year)",height=650)
        return fig
    except Exception as exc:
        fig=go.Figure(); fig.add_annotation(text=f"Error: {exc}",xref="paper",yref="paper",x=0.5,y=0.5,showarrow=False); return fig

def get_research_tree_viz():
    try:
        p = get_p()
        tree = p.warehouse.get_research_tree()
        nodes_flat = p.warehouse.get_flat_list()
        if not nodes_flat:
            fig=go.Figure(); fig.add_annotation(text="No experiments yet. Run a query first.", xref="paper",yref="paper",x=0.5,y=0.5,showarrow=False,font=dict(size=16)); return fig
        labels=[n["title"][:40] for n in nodes_flat]
        parents=[n.get("parent_id","") or "" for n in nodes_flat]
        ids=[n["node_id"] for n in nodes_flat]
        colors={"success":"#22c55e","failed":"#ef4444","inconclusive":"#f59e0b","designed":"#3b82f6","running":"#a855f7"}
        node_colors=[colors.get(n.get("status",""),"#6b7280") for n in nodes_flat]
        fig = go.Figure(go.Treemap(
            ids=ids, labels=labels, parents=parents,
            marker=dict(colors=node_colors),
            hovertemplate="<b>%{label}</b><br>Status: %{customdata}<extra></extra>",
            customdata=[n.get("status","") for n in nodes_flat]))
        fig.update_layout(title="Research Experiment Tree", height=600,
            margin=dict(l=0,r=0,t=40,b=0))
        return fig
    except Exception as exc:
        fig=go.Figure(); fig.add_annotation(text=f"Error: {exc}",xref="paper",yref="paper",x=0.5,y=0.5,showarrow=False); return fig

def get_arena_leaderboard():
    p = get_p()
    entries = p.arena.get_leaderboard(top_n=30)
    if not entries: return "No entries yet. Run a query first."
    stats = p.arena.get_arena_stats()
    md = f"**All-time leaderboard** | Total: {stats.get('total_scored',0)} | Avg score: {stats.get('avg_scientist_score',0)} | Max: {stats.get('max_scientist_score',0)}\n\n"
    md += "| Rank | Title | Score | Novelty | Impact | Feasibility | Venue | Pitch |\n"
    md += "|------|-------|-------|---------|--------|-------------|-------|-------|\n"
    for i,e in enumerate(entries,1):
        md += (f"| {i} | {e.get('title','')[:40]} | **{e.get('scientist_score',0):.1f}** | "
               f"{e.get('novelty_score',0):.0f} | {e.get('expected_impact',0):.0f} | "
               f"{e.get('feasibility_score',0):.0f} | {e.get('estimated_venue','?')} | "
               f"_{e.get('one_line_pitch','')[:40]}_ |\n")
    return md

def get_memory_view(status_filter):
    p = get_p()
    entries = p.memory.all_entries()
    if status_filter != "all": entries = [e for e in entries if e.get("status")==status_filter]
    if not entries: return "No memory entries yet."
    md = f"**Total: {p.memory.total()}** | ✅ {len(p.memory.get_successful_discoveries())} | ❌ {len(p.memory.get_failed_hypotheses())}\n\n---\n\n"
    for e in entries[:25]:
        se = {"success":"✅","failed":"❌","inconclusive":"⚠️","designed":"📐"}.get(e.get("status",""),"❓")
        md += f"### {se} `{e.get('id','')}` — {e.get('hypothesis','')[:80]}\n\n"
        md += f"Status: {e.get('status','')} | Loop: {e.get('loop_iteration',0)} | {e.get('created_at','')[:10]}\n\n"
        if e.get("result_summary"): md += f"Result: {e['result_summary']}\n\n"
        if e.get("failure_reason"): md += f"Failure: {e['failure_reason']}\n\n"
        md += "---\n\n"
    return md

def get_warehouse_stats():
    p = get_p()
    stats = p.warehouse.get_stats()
    failures = p.warehouse.get_failure_patterns()
    successes = p.warehouse.get_success_patterns()
    if not stats.get("total"): return "No experiments in warehouse yet."
    md = f"## Experiment Warehouse\n\n**Total experiments:** {stats['total']}\n\n"
    md += "**By status:**\n"
    for k,v in stats.get("by_status",{}).items(): md += f"- {k}: {v}\n"
    md += "\n**By source:**\n"
    for k,v in stats.get("by_source",{}).items(): md += f"- {k}: {v}\n"
    md += f"\n**Max depth (loop iterations):** {stats.get('max_depth',0)}\n"
    md += f"**Avg scientist score:** {stats.get('avg_scientist_score',0)}\n"
    if failures:
        md += "\n### Failure Patterns Detected\n"
        for f in failures: md += f"- **{f['pattern']}**: {f['count']} experiments — e.g. _{f['examples'][0] if f['examples'] else ''}_\n"
    if successes:
        md += "\n### Successful Discoveries\n"
        for s in successes[:5]: md += f"- **{s['title']}**: {s['key_finding']}\n"
    return md

def generate_twin(name, domain, gaps_text):
    if not domain.strip(): return "Enter a domain."
    try:
        p = get_p()
        if name not in p.twin.list_personas(): p.twin.load_famous_persona(name)
        gaps = [g.strip() for g in gaps_text.split("\n") if g.strip()]
        result = p.twin.generate_twin_hypothesis(name, domain, gaps)
        persona = result.get("persona_summary",{})
        return (f"## 🤖 {name}\n\n"
                f"**Core themes:** {', '.join(persona.get('core_themes',[])[:4])}\n\n"
                f"**Style:** {persona.get('style','')}\n\n---\n\n"
                f"## Hypothesis\n\n{result.get('twin_hypothesis','')}")
    except Exception as exc: return f"Error: {exc}"

def get_dashboard():
    snap = metrics.snapshot()
    p = get_p()
    w_stats = p.warehouse.get_stats()
    arena_stats = p.arena.get_arena_stats()
    md = "## M.A.R.S 4.0 — Live Research Dashboard\n\n"
    md += "| Metric | Value |\n|--------|-------|\n"
    md += f"| 📄 Papers indexed | **{snap['papers_indexed']:,}** |\n"
    md += f"| 🕸️ Graph nodes | **{snap['graph_nodes']:,}** |\n"
    md += f"| 🔗 Cross-paper combos | **{snap['cross_paper_combinations']}** |\n"
    md += f"| 🏆 Arena scored | **{snap['arena_scored']}** |\n"
    md += f"| 🏅 Arena top score | **{arena_stats.get('max_scientist_score',0)}** |\n"
    md += f"| 💡 Hypotheses | **{snap['hypotheses_generated']}** |\n"
    md += f"| ⚔️ Panel rounds | **{snap['debate_rounds']}** |\n"
    md += f"| 🧪 Designed | **{snap['experiments_designed']}** |\n"
    md += f"| ▶️ Run | **{snap['experiments_run']}** |\n"
    md += f"| ✅ Discoveries | **{snap['successful_discoveries']}** |\n"
    md += f"| 📦 Warehouse nodes | **{w_stats.get('total',0)}** |\n"
    md += f"| 🧠 Memory entries | **{snap['memory_entries']}** |\n"
    md += f"| 📈 Success rate | **{snap['experiment_success_rate']}%** |\n"
    md += f"| ⏱️ Avg latency | **{snap['avg_latency_sec']}s** |\n"
    return md

with gr.Blocks(title="M.A.R.S 4.0", theme=gr.themes.Soft(),
    css=".gradio-container{max-width:1250px!important}") as demo:

    gr.Markdown("""
# 🔬 M.A.R.S 4.0 — Research Operating System
**15-node autonomous research pipeline. Not a chatbot.**
Ingest → Graph → Memory → Literature → **Cross-Paper Synthesis** → Hypothesize → **Arena Scoring** → **Specialist Panel** → Experiment Factory → Warehouse → Execute → Analyze → Twin → Loop → Report
    """)

    with gr.Tabs():
        with gr.TabItem("🚀 Research OS"):
            with gr.Row():
                q1 = gr.Textbox(label="Research Query", scale=4,
                    placeholder="e.g. speculative decoding for LLM inference efficiency")
                run_exps = gr.Checkbox(label="Run Experiments", value=True, scale=1)
                twin_sel = gr.Dropdown(choices=["Andrej Karpathy","Andrew Ng","Yann LeCun"],
                    value="Andrej Karpathy", label="Twin", scale=1)
                run_btn = gr.Button("🚀 Run", variant="primary", scale=1)
            # Always-visible status bar
            status_out = gr.Textbox(
                value="Ready — enter a query and click Run. First run takes 3–5 minutes.",
                label="⏱ Status", interactive=False)
            with gr.Row():
                with gr.Column(scale=3): report_out = gr.Markdown(label="📄 Report")
                with gr.Column(scale=1):
                    bench_out = gr.Markdown(label="📊 Benchmarks")
                    gaps_out = gr.Markdown(label="🔍 Research Gaps")
            with gr.Row():
                arena_out = gr.Markdown(label="🏆 Arena Top Hypotheses")
                cp_out = gr.Markdown(label="🔗 Cross-Paper Combos")
            exp_out = gr.Markdown(label="🧪 Experiments")
            twin_out = gr.Markdown(label="🤖 Twin", visible=False)
            run_btn.click(fn=run_full, inputs=[q1, run_exps, twin_sel],
                outputs=[report_out, gaps_out, arena_out, cp_out, exp_out, bench_out, twin_out, status_out])

        with gr.TabItem("🕸️ Citation Graph"):
            gr.Markdown("*Node size = citations. Color = publication year.*")
            gr.Button("Refresh").click(fn=get_graph_viz, outputs=[gr.Plot()])

        with gr.TabItem("🌳 Research Tree"):
            gr.Markdown("*Every experiment as a tree node. Success=green, Failed=red, Designed=blue.*")
            tree_btn = gr.Button("Refresh Tree")
            tree_plot = gr.Plot()
            tree_btn.click(fn=get_research_tree_viz, outputs=[tree_plot])

        with gr.TabItem("🏆 Arena Leaderboard"):
            gr.Markdown("*All-time ranked hypothesis leaderboard across all sessions.*")
            gr.Button("Load Leaderboard").click(fn=get_arena_leaderboard, outputs=[gr.Markdown()])

        with gr.TabItem("🧠 Research Memory"):
            gr.Markdown("*Every hypothesis tried, result, failure reason.*")
            with gr.Row():
                sf = gr.Dropdown(choices=["all","success","failed","inconclusive","designed"],
                    value="all", label="Filter", scale=2)
                gr.Button("Refresh", scale=1).click(fn=get_memory_view, inputs=[sf], outputs=[gr.Markdown()])

        with gr.TabItem("📦 Warehouse"):
            gr.Markdown("*Failure patterns, success patterns, experiment tree stats.*")
            gr.Button("Load Warehouse Stats").click(fn=get_warehouse_stats, outputs=[gr.Markdown()])

        with gr.TabItem("🤖 Research Twin"):
            gr.Markdown("*Generate a hypothesis as a famous researcher would.*")
            with gr.Row():
                tn = gr.Dropdown(choices=["Andrej Karpathy","Andrew Ng","Yann LeCun"],
                    value="Andrej Karpathy", label="Researcher", scale=2)
                td = gr.Textbox(label="Domain", scale=3)
            tg = gr.Textbox(label="Gaps (one per line)", lines=4)
            gr.Button("Generate", variant="primary").click(fn=generate_twin, inputs=[tn,td,tg], outputs=[gr.Markdown()])

        with gr.TabItem("📊 Dashboard"):
            gr.Button("Refresh Dashboard").click(fn=get_dashboard, outputs=[gr.Markdown()])

    gr.Markdown("---\n*M.A.R.S 4.0 — Research Operating System | Powered by Groq + Llama 3.3 70B*")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, share=False)
