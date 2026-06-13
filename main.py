"""M.A.R.S 4.0 — python main.py --query "..." | --ui | --serve"""
import argparse, sys

def run(query, run_experiments=True, twin="Andrej Karpathy"):
    from agents.pipeline import MARSPipeline
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from core import metrics
    console = Console()
    console.print(Panel(f"[bold cyan]M.A.R.S 4.0[/bold cyan] — {query}", expand=False))
    p = MARSPipeline()
    result = p.run(query, run_experiments=run_experiments, twin_persona=twin)
    console.print(Markdown(result.get("final_report","")))
    snap = metrics.snapshot()
    console.print(f"\n[dim]Papers:{snap['papers_indexed']} | Nodes:{result.get('graph_stats',{}).get('nodes',0)} | "
                  f"Arena:{snap['arena_scored']} | Cross-paper:{snap['cross_paper_combinations']} | "
                  f"Discoveries:{snap['successful_discoveries']} | {result.get('latency_sec',0)}s[/dim]")
    p.close()

def serve():
    import uvicorn, os
    from core import config
    # Render / Railway inject PORT at runtime; fall back to config value
    port = int(os.environ.get("PORT", config.API_PORT))
    uvicorn.run("api.server:app", host="0.0.0.0", port=port, reload=False)

def launch_ui():
    import os
    from frontend.app import demo
    # Render exposes the UI on PORT when running the UI service
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, share=False)

if __name__=="__main__":
    p = argparse.ArgumentParser(description="M.A.R.S 4.0")
    p.add_argument("--query"); p.add_argument("--twin", default="Andrej Karpathy")
    p.add_argument("--no-experiments", action="store_true")
    p.add_argument("--serve", action="store_true"); p.add_argument("--ui", action="store_true")
    args = p.parse_args()
    if args.serve: serve()
    elif args.ui: launch_ui()
    elif args.query: run(args.query, not args.no_experiments, args.twin)
    else: p.print_help()
