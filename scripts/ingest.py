"""Pre-ingest papers.
python scripts/ingest.py --queries "LLM inference" "speculative decoding" --max 200
"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.ingestion.arxiv_client import ArxivClient
from services.ingestion.vector_store import VectorStore
from services.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from core.logger import logger
from rich.console import Console
from rich.table import Table

console = Console()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", nargs="+", default=[])
    parser.add_argument("--domain", default="")
    parser.add_argument("--max", type=int, default=100)
    args = parser.parse_args()
    queries = args.queries or ([args.domain] if args.domain else [])
    if not queries:
        console.print("[red]Provide --queries or --domain[/red]"); sys.exit(1)

    console.print(f"\n[bold cyan]M.A.R.S 3.0 — Paper Ingestion[/bold cyan]")
    client = ArxivClient(max_per_query=args.max)
    vs = VectorStore()
    kg = KnowledgeGraphBuilder()

    papers = client.fetch(queries)
    added  = vs.add_papers(papers)
    stats  = kg.ingest_papers(papers)
    clusters = kg.detect_research_clusters()
    gaps     = kg.detect_gaps()
    influential = kg.get_influential_papers(5)

    t = Table(title="Ingestion Results")
    t.add_column("Metric", style="cyan"); t.add_column("Value", style="green")
    t.add_row("Papers fetched", str(len(papers)))
    t.add_row("Added to vector store", str(added))
    t.add_row("Graph nodes", str(stats.get("nodes",0)))
    t.add_row("Graph edges", str(stats.get("edges",0)))
    t.add_row("Research clusters", str(len(clusters)))
    t.add_row("Structural gaps detected", str(len(gaps)))
    console.print(t)

    if influential:
        console.print("\n[bold]Most influential (PageRank):[/bold]")
        for p in influential:
            console.print(f"  • {p.get('title','')[:80]} (citations: {p.get('citation_count',0)})")
    if gaps[:3]:
        console.print("\n[bold]Top structural gaps:[/bold]")
        for g in gaps[:3]:
            console.print(f"  • {g.get('description','')}")

    kg.close()
    console.print("\n[green]✓ Ingestion complete[/green]")

if __name__ == "__main__":
    main()
