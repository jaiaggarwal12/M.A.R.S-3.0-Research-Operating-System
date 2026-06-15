from __future__ import annotations
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List
import arxiv
from core.logger import logger
from core import config, metrics


@dataclass
class PaperRecord:
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    published: str
    updated: str
    categories: List[str]
    pdf_url: str
    entry_url: str
    citation_count: int = 0
    references: List[str] = field(default_factory=list)
    influential_citation_count: int = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @property
    def year(self) -> int:
        try: return int(self.published[:4])
        except: return 0


class ArxivClient:
    def __init__(self, max_per_query=config.MAX_PAPERS_PER_QUERY, max_age_days=config.MAX_PAPER_AGE_DAYS):
        self.max_per_query = min(max_per_query, 15)  # Cap at 15 for speed on cloud
        self.max_age_days = max_age_days
        self._client = arxiv.Client(page_size=20, delay_seconds=1.0, num_retries=2)

    def fetch(self, queries: List[str]) -> List[PaperRecord]:
        seen, papers = set(), []
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        for query in queries:
            logger.info(f"[Ingestion] '{query}'")
            try:
                for r in self._client.results(arxiv.Search(
                    query=query, max_results=self.max_per_query,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending)):
                    if r.published < cutoff: continue
                    aid = r.get_short_id()
                    if aid in seen: continue
                    seen.add(aid)
                    papers.append(self._to_record(r))
            except Exception as exc:
                logger.warning(f"[Ingestion] Arxiv error: {exc}")
            time.sleep(0.5)

        if config.FETCH_CITATIONS and config.SEMANTIC_SCHOLAR_API_KEY:
            papers = self._enrich(papers)

        metrics.inc("papers_indexed", len(papers))
        return papers

    def _enrich(self, papers):
        try:
            import requests
            ids = [f"ARXIV:{p.arxiv_id}" for p in papers[:100]]
            resp = requests.post(
                "https://api.semanticscholar.org/graph/v1/paper/batch",
                json={"ids": ids},
                params={"fields": "citationCount,influentialCitationCount,references"},
                headers={"x-api-key": config.SEMANTIC_SCHOLAR_API_KEY},
                timeout=30)
            if resp.status_code == 200:
                for p, e in zip(papers, resp.json()):
                    if e:
                        p.citation_count = e.get("citationCount", 0)
                        p.influential_citation_count = e.get("influentialCitationCount", 0)
                        p.references = [r.get("externalIds",{}).get("ArXiv","") for r in e.get("references",[]) if r.get("externalIds",{}).get("ArXiv")]
        except Exception as exc:
            logger.warning(f"[Ingestion] S2 enrichment failed: {exc}")
        return papers

    @staticmethod
    def _to_record(r: arxiv.Result) -> PaperRecord:
        return PaperRecord(
            arxiv_id=r.get_short_id(), title=r.title.strip(),
            authors=[str(a) for a in r.authors], abstract=r.summary.strip(),
            published=r.published.isoformat(), updated=r.updated.isoformat(),
            categories=r.categories, pdf_url=r.pdf_url or "", entry_url=r.entry_id)
