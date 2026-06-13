"""
Build large-scale paper corpus.

python scripts/build_corpus.py --domain "LLM inference" --target 10000
python scripts/build_corpus.py --domain "graph neural networks" --target 50000 --workers 8
python scripts/build_corpus.py --categories cs.LG cs.AI cs.CL --target 20000
"""
import argparse, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ingestion.vector_store import VectorStore
from services.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from services.corpus.bulk_corpus_loader import BulkCorpusLoader
from core.logger import logger
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, MofNCompleteColumn
from rich.table import Table

console = Console()


def main():
    parser = argparse.ArgumentParser(description="M.A.R.S Corpus Builder")
    parser.add_argument("--domain", type=str, default="", help="Research domain query")
    parser.add_argument("--queries", nargs="+", default=[], help="Multiple queries")
    parser.add_argument("--categories", nargs="+", default=[], help="Arxiv categories e.g. cs.LG")
    parser.add_argument("--target", type=int, default=10_000, help="Target paper count")
    parser.add_argument("--workers", type=int, default=4, help="Parallel fetch threads")
    parser.add_argument("--no-snowball", action="store_true", help="Skip citation snowballing")
    args = parser.parse_args()

    queries = args.queries or ([args.domain] if args.domain else [])
    if not queries:
        console.print("[red]Provide --domain or --queries[/red]")
        sys.exit(1)

    console.print(f"\n[bold cyan]M.A.R.S 4.0 — Corpus Builder[/bold cyan]")
    console.print(f"Target: {args.target:,} papers | Queries: {queries} | Workers: {args.workers}")
    if args.categories:
        console.print(f"Categories: {args.categories}")

    vs = VectorStore()
    kg = KnowledgeGraphBuilder()
    loader = BulkCorpusLoader(vs, kg, target=args.target)

    # Progress bar
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing papers", total=args.target)
        current = [vs.total()]

        def on_progress(n, total, msg):
            delta = n - current[0]
            current[0] = n
            progress.update(task, advance=delta, description=msg[:50])

        loader.set_progress_callback(on_progress)
        t0 = time.time()
        stats = loader.build_corpus(
            seed_queries=queries,
            categories=args.categories or None,
            use_snowball=not args.no_snowball,
            max_workers=args.workers,
        )
        elapsed = round(time.time() - t0, 1)

    t = Table(title=f"Corpus Built in {elapsed}s")
    t.add_column("Metric", style="cyan")
    t.add_column("Value", style="green")
    t.add_row("Total papers indexed", f"{stats.total_papers:,}")
    t.add_row("Target", f"{args.target:,}")
    t.add_row("Completion", f"{min(100, round(stats.total_papers/args.target*100, 1))}%")
    t.add_row("Vector store total", f"{vs.total():,}")
    t.add_row("Graph nodes", f"{kg.total_papers():,}")
    t.add_row("Elapsed", f"{elapsed}s")
    console.print(t)

    if stats.by_category:
        console.print("\n[bold]Top categories:[/bold]")
        for cat, count in list(stats.by_category.items())[:10]:
            console.print(f"  {cat}: {count:,}")

    clusters = kg.detect_research_clusters()
    gaps = kg.detect_gaps()
    console.print(f"\n[green]✓ {len(clusters)} research clusters | {len(gaps)} structural gaps detected[/green]")

    kg.close()


if __name__ == "__main__":
    main()
