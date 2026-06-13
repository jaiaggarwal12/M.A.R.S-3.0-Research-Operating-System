from __future__ import annotations
from itertools import combinations
from typing import Dict, List
import networkx as nx
from core.logger import logger
from core import config, metrics
from services.ingestion.arxiv_client import PaperRecord

try:
    from neo4j import GraphDatabase; _NEO4J = True
except ImportError:
    _NEO4J = False


class KnowledgeGraphBuilder:
    def __init__(self):
        self._driver = None
        self._nx: nx.DiGraph = nx.DiGraph()
        self._papers: Dict[str, dict] = {}
        if _NEO4J:
            try:
                self._driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
                self._driver.verify_connectivity()
                self._db = config.NEO4J_DATABASE
                self._init_schema()
                logger.info(f"KnowledgeGraph: Neo4j Aura connected (db={self._db})")
            except Exception as exc:
                logger.warning(f"KnowledgeGraph: NetworkX fallback ({exc})")
                self._driver = None
                self._db = "neo4j"

    def ingest_papers(self, papers: List[PaperRecord]) -> Dict:
        for p in papers:
            self._papers[p.arxiv_id] = p.to_dict()
            self._nx.add_node(p.arxiv_id, title=p.title, abstract=p.abstract,
                published=p.published, categories=p.categories,
                authors=p.authors, citation_count=p.citation_count)
            for ref in p.references:
                if ref: self._nx.add_edge(p.arxiv_id, ref, rel="CITES")
        if self._driver:
            with self._driver.session(database=self._db) as s:
                for p in papers: s.execute_write(self._upsert_tx, p)
        stats = self._stats()
        metrics.inc("graph_nodes", stats["nodes"])
        metrics.inc("graph_edges", stats["edges"])
        return stats

    def get_influential_papers(self, top_n=10) -> List[dict]:
        if not self._nx.nodes: return []
        try:
            pr = nx.pagerank(self._nx, alpha=0.85, max_iter=200)
            top = sorted(pr, key=lambda x: -pr[x])[:top_n]
            return [{**self._papers[i], "pagerank_score": round(pr[i],6)} for i in top if i in self._papers]
        except Exception:
            return sorted(self._papers.values(), key=lambda x: -x.get("citation_count",0))[:top_n]

    def detect_research_clusters(self, min_size=3) -> List[dict]:
        if len(self._nx.nodes) < min_size: return []
        ug = self._nx.to_undirected()
        clusters = []
        for i, comp in enumerate(nx.connected_components(ug)):
            if len(comp) < min_size: continue
            sub = ug.subgraph(comp)
            cats = []
            for pid in comp: cats.extend(self._nx.nodes.get(pid,{}).get("categories",[]))
            tc: dict = {}
            for c in cats: tc[c] = tc.get(c,0)+1
            top_topics = sorted(tc, key=lambda x: -tc[x])[:3]
            rep = max(dict(sub.degree()), key=lambda x: dict(sub.degree())[x])
            clusters.append({
                "cluster_id": i, "size": len(comp), "topics": top_topics,
                "representative_paper": self._papers.get(rep,{}).get("title",""),
                "paper_ids": list(comp)[:20], "density": round(nx.density(sub),4)})
        clusters.sort(key=lambda x: -x["size"])
        return clusters

    def detect_gaps(self) -> List[dict]:
        if len(self._papers) < 5: return []
        co: dict = {}; solo: dict = {}
        for p in self._papers.values():
            cats = p.get("categories",[])
            for c in cats: solo[c] = solo.get(c,0)+1
            for a,b in combinations(sorted(cats),2):
                k=(a,b); co[k]=co.get(k,0)+1
        gaps = []
        for a, ca in solo.items():
            if ca < 3: continue
            for b, cb in solo.items():
                if a >= b or cb < 3: continue
                together = co.get((a,b),0)
                if together == 0 and ca >= 5 and cb >= 5:
                    gaps.append({"topic_a":a,"topic_b":b,"papers_in_a":ca,
                        "papers_in_b":cb,"papers_combining_both":0,
                        "gap_score":ca+cb,
                        "description":f"No papers combine {a} and {b} despite both being active ({ca}+{cb} papers)"})
        gaps.sort(key=lambda x:-x["gap_score"])
        metrics.inc("novel_gaps_found", len(gaps[:10]))
        return gaps[:15]

    def get_citation_network_json(self, max_nodes=100) -> dict:
        nodes_data = list(self._nx.nodes(data=True))[:max_nodes]
        node_ids = {n[0] for n in nodes_data}
        return {
            "nodes": [{"id":nid,"title":d.get("title",nid)[:60],"year":d.get("published","")[:4],
                "citations":d.get("citation_count",0),"categories":d.get("categories",[])[:2]}
                for nid,d in nodes_data],
            "edges": [{"source":u,"target":v} for u,v in self._nx.edges()
                if u in node_ids and v in node_ids]}

    def get_topic_landscape(self) -> List[dict]:
        tc: dict = {}
        for p in self._papers.values():
            for c in p.get("categories",[]): tc[c]=tc.get(c,0)+1
        return [{"topic":t,"paper_count":c} for t,c in sorted(tc.items(),key=lambda x:-x[1])]

    def total_papers(self) -> int: return len(self._papers)
    def close(self):
        if self._driver: self._driver.close()

    def _stats(self) -> dict:
        g = self._nx
        return {"nodes":g.number_of_nodes(),"edges":g.number_of_edges(),
            "connected_components":nx.number_weakly_connected_components(g),
            "avg_degree":round(sum(d for _,d in g.degree())/max(g.number_of_nodes(),1),2)}

    @staticmethod
    def _upsert_tx(tx, p):
        tx.run("MERGE (n:Paper {arxiv_id:$id}) SET n.title=$t,n.abstract=$a,n.published=$pub,n.citation_count=$c",
            id=p.arxiv_id,t=p.title,a=p.abstract,pub=p.published,c=p.citation_count)

    def _init_schema(self):
        with self._driver.session(database=self._db) as s:
            for q in ["CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.arxiv_id IS UNIQUE"]:
                try: s.run(q)
                except: pass
