"""
Bulk Corpus Loader

Gets MARS to 10k–100k papers — the scale where the knowledge graph
becomes genuinely informative and gap detection gets meaningful signal.

Strategy (in order of scale):
  1. Arxiv multi-query parallel fetch     →  500–5k papers
  2. Semantic Scholar bulk API            →  5k–50k papers
  3. S2ORC open corpus (if available)     →  100k+ papers
  4. Citation snowballing                 →  fills gaps in citation graph

At 10k papers:
  - Graph has ~10k nodes, potentially 50k+ edges
  - Topic co-occurrence matrix has statistical power
  - Cross-paper synthesis draws from a real ingredient space
  - Gap detection identifies genuinely under-explored intersections

Corpus is built incrementally — safe to interrupt and resume.
"""
from __future__ import annotations
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from core.logger import logger
from core import config, metrics


@dataclass
class CorpusStats:
    total_papers: int = 0
    by_source: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    date_range: tuple = ("", "")
    last_updated: str = ""


class BulkCorpusLoader:
    """
    Parallel paper ingestion at scale.
    Designed to hit 10k+ papers before returning.
    """

    def __init__(self, vector_store, kg, target: int = 10_000):
        self._vs = vector_store
        self._kg = kg
        self._target = target
        self._seen: Set[str] = set()
        self._lock = threading.Lock()
        self._stats = CorpusStats()
        self._progress_cb: Optional[Callable] = None

        # Load existing IDs to avoid re-indexing
        self._load_existing()

    def set_progress_callback(self, cb: Callable[[int, int, str], None]):
        """cb(current, target, message)"""
        self._progress_cb = cb

    def build_corpus(
        self,
        seed_queries: List[str],
        categories: Optional[List[str]] = None,
        use_snowball: bool = True,
        max_workers: int = 4,
    ) -> CorpusStats:
        """
        Main entry point. Fetches papers until target is reached.

        Args:
            seed_queries: Initial Arxiv queries to start from
            categories: Arxiv category filters (e.g. ["cs.LG", "cs.AI"])
            use_snowball: Whether to follow citation links
            max_workers: Parallel fetch threads
        """
        logger.info(f"[Corpus] Building to {self._target:,} papers. "
                    f"Starting with {len(self._seen):,} existing.")
        self._emit_progress(len(self._seen), "Starting corpus build")

        # Phase 1: Arxiv parallel multi-query
        if len(self._seen) < self._target:
            self._arxiv_parallel(seed_queries, categories, max_workers)

        # Phase 2: Semantic Scholar bulk API (if key available)
        if len(self._seen) < self._target and config.SEMANTIC_SCHOLAR_API_KEY:
            self._semantic_scholar_bulk(seed_queries)

        # Phase 3: Citation snowballing (follow reference chains)
        if use_snowball and len(self._seen) < self._target:
            self._citation_snowball()

        self._stats.total_papers = len(self._seen)
        self._stats.last_updated = datetime.now().isoformat()
        self._emit_progress(len(self._seen), "Corpus build complete")
        logger.info(f"[Corpus] Final corpus size: {len(self._seen):,} papers")
        return self._stats

    # ── Phase 1: Arxiv parallel ──────────────────────────────────────────────

    def _arxiv_parallel(
        self,
        queries: List[str],
        categories: Optional[List[str]],
        max_workers: int,
    ):
        """Fetch multiple Arxiv queries in parallel threads."""
        import arxiv
        from services.ingestion.arxiv_client import PaperRecord

        # Expand query list with category variants
        expanded = list(queries)
        if categories:
            for cat in categories:
                for q in queries[:3]:
                    expanded.append(f"cat:{cat} AND {q}")

        # Also add time-sliced queries to get more coverage
        years = ["2024", "2023", "2022"]
        base_queries = queries[:3]
        for year in years:
            for q in base_queries:
                expanded.append(f"{q} {year}")

        logger.info(f"[Corpus] Phase 1: {len(expanded)} Arxiv queries, {max_workers} threads")

        client = arxiv.Client(page_size=100, delay_seconds=2.0, num_retries=5)

        def fetch_one(query: str) -> List[PaperRecord]:
            if len(self._seen) >= self._target:
                return []
            papers = []
            try:
                results = client.results(arxiv.Search(
                    query=query,
                    max_results=min(500, self._target // max(len(expanded), 1) + 100),
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                ))
                for r in results:
                    if len(self._seen) >= self._target:
                        break
                    aid = r.get_short_id()
                    with self._lock:
                        if aid in self._seen:
                            continue
                        self._seen.add(aid)
                    papers.append(PaperRecord(
                        arxiv_id=aid, title=r.title.strip(),
                        authors=[str(a) for a in r.authors],
                        abstract=r.summary.strip(),
                        published=r.published.isoformat(),
                        updated=r.updated.isoformat(),
                        categories=r.categories,
                        pdf_url=r.pdf_url or "",
                        entry_url=r.entry_id,
                    ))
                time.sleep(1)
            except Exception as exc:
                logger.warning(f"[Corpus] Arxiv fetch failed for '{query}': {exc}")
            return papers

        all_papers = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(fetch_one, q): q for q in expanded}
            for future in as_completed(futures):
                batch = future.result()
                if batch:
                    all_papers.extend(batch)
                    # Index in chunks of 200
                    if len(all_papers) >= 200:
                        self._index_batch(all_papers[:200])
                        all_papers = all_papers[200:]
                        self._emit_progress(len(self._seen),
                                            f"Phase 1: {len(self._seen):,} papers indexed")

        if all_papers:
            self._index_batch(all_papers)

        logger.info(f"[Corpus] Phase 1 complete: {len(self._seen):,} papers")

    # ── Phase 2: Semantic Scholar bulk ───────────────────────────────────────

    def _semantic_scholar_bulk(self, queries: List[str]):
        """
        Semantic Scholar API bulk search.
        Returns up to 10M papers via pagination.
        Rate limit: 100 req/5min without key, 1 req/sec with key.
        """
        import requests

        headers = {}
        if config.SEMANTIC_SCHOLAR_API_KEY:
            headers["x-api-key"] = config.SEMANTIC_SCHOLAR_API_KEY

        logger.info(f"[Corpus] Phase 2: Semantic Scholar bulk fetch")

        for query in queries[:5]:
            if len(self._seen) >= self._target:
                break

            offset = 0
            limit = 100
            while len(self._seen) < self._target:
                try:
                    resp = requests.get(
                        "https://api.semanticscholar.org/graph/v1/paper/search",
                        params={
                            "query": query,
                            "offset": offset,
                            "limit": limit,
                            "fields": "paperId,externalIds,title,abstract,authors,year,citationCount,references",
                        },
                        headers=headers,
                        timeout=30,
                    )

                    if resp.status_code == 429:
                        logger.warning("[Corpus] S2 rate limit — sleeping 30s")
                        time.sleep(30)
                        continue

                    if resp.status_code != 200:
                        break

                    data = resp.json()
                    papers_data = data.get("data", [])
                    if not papers_data:
                        break

                    batch = []
                    for p in papers_data:
                        arxiv_id = p.get("externalIds", {}).get("ArXiv", "")
                        if not arxiv_id or arxiv_id in self._seen:
                            continue
                        with self._lock:
                            self._seen.add(arxiv_id)

                        from services.ingestion.arxiv_client import PaperRecord
                        batch.append(PaperRecord(
                            arxiv_id=arxiv_id,
                            title=p.get("title", "")[:500],
                            authors=[a.get("name", "") for a in p.get("authors", [])[:10]],
                            abstract=p.get("abstract", "") or "",
                            published=f"{p.get('year','2020')}-01-01T00:00:00+00:00",
                            updated=f"{p.get('year','2020')}-01-01T00:00:00+00:00",
                            categories=["cs.LG"],  # S2 doesn't return arxiv categories
                            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
                            entry_url=f"https://arxiv.org/abs/{arxiv_id}",
                            citation_count=p.get("citationCount", 0),
                        ))

                    if batch:
                        self._index_batch(batch)
                        self._emit_progress(len(self._seen),
                                            f"Phase 2: {len(self._seen):,} papers (S2)")

                    if len(papers_data) < limit:
                        break
                    offset += limit
                    time.sleep(1)

                except Exception as exc:
                    logger.warning(f"[Corpus] S2 error: {exc}")
                    break

        logger.info(f"[Corpus] Phase 2 complete: {len(self._seen):,} papers")

    # ── Phase 3: Citation snowballing ────────────────────────────────────────

    def _citation_snowball(self):
        """
        Follow citation links to expand corpus.
        Takes highly-cited papers already in graph, fetches their references.
        """
        logger.info(f"[Corpus] Phase 3: Citation snowballing")

        influential = self._kg.get_influential_papers(top_n=50)
        arxiv_ids_to_expand = [
            p["arxiv_id"] for p in influential
            if p.get("arxiv_id") and p.get("citation_count", 0) > 10
        ][:20]

        if not arxiv_ids_to_expand:
            return

        import arxiv
        from services.ingestion.arxiv_client import PaperRecord

        client = arxiv.Client(page_size=50, delay_seconds=2.0, num_retries=3)
        snowballed = []

        for paper_id in arxiv_ids_to_expand:
            if len(self._seen) >= self._target:
                break
            try:
                # Fetch papers that cite this influential paper
                results = client.results(arxiv.Search(
                    query=f"cite:{paper_id}",
                    max_results=100,
                ))
                for r in results:
                    if len(self._seen) >= self._target: break
                    aid = r.get_short_id()
                    with self._lock:
                        if aid in self._seen: continue
                        self._seen.add(aid)
                    snowballed.append(PaperRecord(
                        arxiv_id=aid, title=r.title.strip(),
                        authors=[str(a) for a in r.authors],
                        abstract=r.summary.strip(),
                        published=r.published.isoformat(),
                        updated=r.updated.isoformat(),
                        categories=r.categories,
                        pdf_url=r.pdf_url or "",
                        entry_url=r.entry_id,
                    ))
                time.sleep(2)
            except Exception:
                pass

        if snowballed:
            self._index_batch(snowballed)
            self._emit_progress(len(self._seen),
                                f"Phase 3: {len(self._seen):,} papers (snowball +{len(snowballed)})")

        logger.info(f"[Corpus] Phase 3 complete: {len(self._seen):,} papers")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _index_batch(self, papers):
        if not papers: return
        try:
            self._vs.add_papers(papers)
            self._kg.ingest_papers(papers)
            metrics.inc("papers_indexed", len(papers))
            for p in papers:
                for cat in p.categories:
                    self._stats.by_category[cat] = self._stats.by_category.get(cat, 0) + 1
        except Exception as exc:
            logger.warning(f"[Corpus] Batch index error: {exc}")

    def _load_existing(self):
        """Load existing arxiv IDs from vector store to skip re-indexing."""
        try:
            # Query vector store metadata
            if hasattr(self._vs, '_meta'):
                for m in self._vs._meta:
                    aid = m.get("arxiv_id", "")
                    if aid:
                        self._seen.add(aid)
            logger.info(f"[Corpus] Loaded {len(self._seen):,} existing IDs")
        except Exception:
            pass

    def _emit_progress(self, current: int, message: str):
        if self._progress_cb:
            try:
                self._progress_cb(current, self._target, message)
            except Exception:
                pass

    def get_stats(self) -> Dict:
        return {
            "total_papers": len(self._seen),
            "target": self._target,
            "progress_pct": round(len(self._seen) / max(self._target, 1) * 100, 1),
            "by_category": dict(sorted(
                self._stats.by_category.items(),
                key=lambda x: -x[1])[:10]),
            "graph_nodes": self._kg.total_papers(),
            "vector_store_total": self._vs.total(),
        }
