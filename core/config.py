from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

for _d in ["logs","faiss_index","experiments","papers","reports","memory","twin_papers"]:
    (DATA_DIR / _d).mkdir(parents=True, exist_ok=True)

# LLM
LLM_PROVIDER: str        = os.getenv("LLM_PROVIDER", "openai")
OPENAI_API_KEY: str      = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str        = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY: str   = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str     = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
OLLAMA_BASE_URL: str     = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str        = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
TEMPERATURE: float       = float(os.getenv("TEMPERATURE", "0.1"))

# Neo4j
NEO4J_URI: str      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER: str     = os.getenv("NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j"))
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

# Vector
FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", str(DATA_DIR/"faiss_index"))
EMBEDDING_MODEL: str  = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Semantic Scholar
SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
FETCH_CITATIONS: bool         = os.getenv("FETCH_CITATIONS","true").lower()=="true"

# Ingestion
MAX_PAPERS_PER_QUERY: int = int(os.getenv("MAX_PAPERS_PER_QUERY", "100"))
MAX_PAPER_AGE_DAYS: int   = int(os.getenv("MAX_PAPER_AGE_DAYS", "730"))
MAX_PAPERS_IN_CONTEXT: int = 12

# Memory
MEMORY_DB_PATH: str       = os.getenv("MEMORY_DB_PATH", str(DATA_DIR/"memory"/"research_memory.json"))
EXPERIMENT_HISTORY_DB: str = os.getenv("EXPERIMENT_HISTORY_DB", str(DATA_DIR/"memory"/"experiments.db"))

# Autonomous loop
MAX_LOOP_ITERATIONS: int  = int(os.getenv("MAX_LOOP_ITERATIONS", "5"))
AUTO_LOOP_ENABLED: bool   = os.getenv("AUTO_LOOP_ENABLED","false").lower()=="true"

# Experiment runner
EXPERIMENT_RUNNER: str    = os.getenv("EXPERIMENT_RUNNER", "local")
EXPERIMENT_TIMEOUT: int   = int(os.getenv("EXPERIMENT_TIMEOUT_SECONDS", "300"))
EXPERIMENTS_DIR: str      = os.getenv("EXPERIMENTS_DIR", str(DATA_DIR/"experiments"))

# Twin
TWIN_PAPERS_DIR: str = os.getenv("TWIN_PAPERS_DIR", str(DATA_DIR/"twin_papers"))

# API
API_HOST: str  = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int  = int(os.getenv("API_PORT", "8000"))
METRICS_PORT: int = int(os.getenv("METRICS_PORT", "9090"))
ENABLE_PROMETHEUS: bool = os.getenv("ENABLE_PROMETHEUS","false").lower()=="true"

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str  = os.getenv("LOG_FILE", str(DATA_DIR/"logs"/"mars.log"))
