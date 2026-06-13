from __future__ import annotations
import pickle
from pathlib import Path
from typing import List, Tuple
import numpy as np
from core.logger import logger
from core import config
from services.ingestion.arxiv_client import PaperRecord

try:
    import faiss; _FAISS = True
except ImportError:
    _FAISS = False

class VectorStore:
    def __init__(self, index_path=config.FAISS_INDEX_PATH, model_name=config.EMBEDDING_MODEL):
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self._fi = self.index_path / "index.faiss"
        self._fm = self.index_path / "meta.pkl"
        self._model_name = model_name
        self._model = None          # lazy — loaded on first encode
        self._dim = None
        self._index = None
        self._meta: List[dict] = []
        if self._fi.exists() and self._fm.exists():
            self._load()

    # ── lazy model loader ────────────────────────────────────
    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"[VectorStore] Loading embedding model {self._model_name}...")
            self._model = SentenceTransformer(self._model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
        return self._model

    def add_papers(self, papers: List[PaperRecord]) -> int:
        existing = {m["arxiv_id"] for m in self._meta}
        new = [p for p in papers if p.arxiv_id not in existing]
        if not new: return 0
        model = self._get_model()
        embs = model.encode([f"{p.title}. {p.abstract}" for p in new],
            batch_size=32, show_progress_bar=False, normalize_embeddings=True).astype("float32")
        if self._index is None:
            self._index = faiss.IndexFlatIP(self._dim) if _FAISS else _NumpyIndex(self._dim)
        self._index.add(embs)
        self._meta.extend([p.to_dict() for p in new])
        self._save(); return len(new)

    def search(self, query: str, k: int = 10) -> List[Tuple[dict, float]]:
        if not self._meta: return []
        model = self._get_model()
        q = model.encode([query], normalize_embeddings=True).astype("float32")
        k = min(k, len(self._meta))
        d, i = self._index.search(q, k)
        return [(self._meta[idx], float(sc)) for sc, idx in zip(d[0], i[0]) if idx >= 0]

    def total(self) -> int: return len(self._meta)

    def _save(self):
        if _FAISS: faiss.write_index(self._index, str(self._fi))
        else:
            with open(self._fi, "wb") as f: pickle.dump(self._index, f)
        with open(self._fm, "wb") as f: pickle.dump(self._meta, f)

    def _load(self):
        if _FAISS: self._index = faiss.read_index(str(self._fi))
        else:
            with open(self._fi, "rb") as f: self._index = pickle.load(f)
        with open(self._fm, "rb") as f: self._meta = pickle.load(f)
        logger.info(f"VectorStore: {len(self._meta)} papers loaded")

class _NumpyIndex:
    def __init__(self, dim): self._v = None
    def add(self, e): self._v = e if self._v is None else np.vstack([self._v, e])
    def search(self, q, k):
        s = (self._v @ q.T).squeeze()
        if s.ndim == 0: s = np.array([float(s)])
        i = np.argsort(s)[::-1][:k]
        return s[i].reshape(1,-1), i.reshape(1,-1)
