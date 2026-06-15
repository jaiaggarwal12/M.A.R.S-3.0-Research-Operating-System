from __future__ import annotations
import os
import pickle
from pathlib import Path
from typing import List, Tuple
from core.logger import logger
from core import config
from services.ingestion.arxiv_client import PaperRecord

class VectorStore:
    """Lightweight vector store — uses TF-IDF on free tier to avoid OOM from sentence-transformers."""
    def __init__(self, index_path=config.FAISS_INDEX_PATH, model_name=config.EMBEDDING_MODEL):
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self._fm = self.index_path / "meta.pkl"
        self._meta: List[dict] = []
        self._use_light = os.environ.get("LIGHT_EMBEDDINGS", "true").lower() == "true"
        self._tfidf = None
        self._tfidf_matrix = None
        if self._fm.exists():
            self._load_meta()

    def add_papers(self, papers) -> int:
        existing = {m["arxiv_id"] for m in self._meta}
        new = [p for p in papers if p.arxiv_id not in existing]
        if not new: return 0
        self._meta.extend([p.to_dict() for p in new])
        self._rebuild_index()
        self._save_meta()
        return len(new)

    def search(self, query: str, k: int = 10) -> List[Tuple[dict, float]]:
        if not self._meta: return []
        self._ensure_index()
        from sklearn.metrics.pairwise import cosine_similarity
        q_vec = self._tfidf.transform([query])
        scores = cosine_similarity(q_vec, self._tfidf_matrix).flatten()
        k = min(k, len(self._meta))
        top_idx = scores.argsort()[::-1][:k]
        return [(self._meta[i], float(scores[i])) for i in top_idx if scores[i] > 0]

    def total(self) -> int: return len(self._meta)

    def _rebuild_index(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        corpus = [f"{m.get('title','')}. {m.get('abstract','')}" for m in self._meta]
        self._tfidf = TfidfVectorizer(max_features=5000, stop_words="english")
        self._tfidf_matrix = self._tfidf.fit_transform(corpus)

    def _ensure_index(self):
        if self._tfidf is None or self._tfidf_matrix is None:
            self._rebuild_index()

    def _save_meta(self):
        with open(self._fm, "wb") as f: pickle.dump(self._meta, f)

    def _load_meta(self):
        with open(self._fm, "rb") as f: self._meta = pickle.load(f)
        logger.info(f"VectorStore: {len(self._meta)} papers loaded (TF-IDF mode)")
