"""M.A.R.S 4.0 LangGraph node factories"""
from __future__ import annotations
import json
from typing import Callable
from langchain_core.messages import SystemMessage, HumanMessage
from core.state import MARSState
from core.llm import get_llm
from core.logger import logger
from core import config

QPROMPT = """Generate exactly 3 Arxiv search queries for the topic below.
Rules: each query MUST contain keywords from the topic. No tangential topics.
Example for "speculative decoding LLM inference": 
["speculative decoding language model inference", "draft model verification LLM speed", "token prediction parallelism transformer inference"]
Return ONLY a JSON array of 3 strings, no explanation."""
ROUTER = "Classify retrieval: graph|vector|hybrid. ONE word only."
LIT_PROMPT = "Write concise literature review (<400 words). Cover themes, key papers, evolution, benchmarks."
LOOP_PROMPT = """Given experiment results, decide: run another loop?
Return JSON: {"continue": true|false, "reasoning": "...", "next_focus": "refined query"}"""

def make_ingest_node(arxiv_client, vector_store):
    def ingest(state):
        query = state["query"]
        # Always use the raw query as first search — guaranteed on-topic
        direct_queries = [query]
        llm = get_llm(temperature=0.1)
        resp = llm.invoke([SystemMessage(content=QPROMPT), HumanMessage(content=f"Topic: {query}")])
        try:
            raw = resp.content.strip().replace("```json","").replace("```","")
            llm_queries = json.loads(raw)
            if isinstance(llm_queries, list):
                topic_words = set(query.lower().split())
                filtered = [q for q in llm_queries
                            if any(w in q.lower() for w in topic_words if len(w) > 3)]
                direct_queries += filtered[:2]
        except:
            pass
        queries = direct_queries[:3]
        logger.info(f"[Ingest] Queries: {queries}")
        # Clear old cached papers so fresh topic-relevant papers are fetched
        vector_store._meta = []
        vector_store._tfidf = None
        vector_store._tfidf_matrix = None
        papers = arxiv_client.fetch(queries)
        vector_store.add_papers(papers)
        return {**state, "papers":[p.to_dict() for p in papers],
                "search_queries":queries, "papers_count":len(papers), "stage":"ingested"}
    return ingest

def make_graph_node(kg):
    def build_graph(state):
        from services.ingestion.arxiv_client import PaperRecord
        papers = [PaperRecord(**{k:v for k,v in d.items() if k in PaperRecord.__dataclass_fields__})
                  for d in state.get("papers",[])]
        stats = kg.ingest_papers(papers)
        return {**state, "graph_stats":stats,
                "research_clusters":kg.detect_research_clusters(),
                "influential_papers":kg.get_influential_papers(10),
                "_graph_gaps":kg.detect_gaps(),
                "citation_network":kg.get_citation_network_json(150), "stage":"graph_built"}
    return build_graph

def make_memory_node(memory):
    def memory_lookup(state):
        query = state.get("query","")
        entries = memory.get_relevant_memory(query, query, top_k=8)
        logger.info(f"[Memory] {len(entries)} prior experiments")
        return {**state, "memory_context":entries, "stage":"memory_checked"}
    return memory_lookup

def make_literature_node(vector_store, kg):
    def literature(state):
        query = state["query"]
        llm = get_llm(temperature=0.0)
        mode = llm.invoke([SystemMessage(content=ROUTER), HumanMessage(content=query)]).content.strip().lower()
        if mode not in ("graph","vector","hybrid"): mode = "hybrid"
        vector_results = []
        if mode in ("vector","hybrid"):
            vector_results = [{"paper":r[0],"score":r[1]}
                               for r in vector_store.search(query, k=config.MAX_PAPERS_IN_CONTEXT)]
        seen, merged = set(), []
        for item in vector_results:
            aid = item["paper"].get("arxiv_id","")
            if aid not in seen: seen.add(aid); merged.append(item["paper"])
        for p in state.get("influential_papers",[]):
            if p.get("arxiv_id","") not in seen:
                seen.add(p["arxiv_id"]); merged.append(p)
        context = "\n\n".join(
            f"[{i+1}] {p.get('title','')}\nAbstract: {p.get('abstract','')[:350]}..."
            for i,p in enumerate(merged[:10]))
        summary = llm.invoke([SystemMessage(content=LIT_PROMPT),
                               HumanMessage(content=f"Query: {query}\n\nPapers:\n{context}")]).content
        return {**state, "vector_results":vector_results, "retrieval_mode":mode,
                "literature_summary":summary, "key_papers":merged[:10], "stage":"literature_done"}
    return literature

def make_cross_paper_node(reasoner):
    def cross_paper(state):
        papers = state.get("key_papers",[])
        gaps = state.get("research_gaps",[]) or [g.get("description","") for g in state.get("_graph_gaps",[])]
        if not papers:
            return {**state, "cross_paper_combinations":[], "stage":"cross_paper_done"}
        components = reasoner.decompose_papers(papers)
        combinations = reasoner.find_combinations(papers, gaps)
        return {**state, "paper_components":components,
                "cross_paper_combinations":combinations,
                "component_matrix":reasoner.get_component_matrix(),
                "stage":"cross_paper_done"}
    return cross_paper

def make_hypothesis_node(hyp_gen, reasoner):
    def hypothesize(state):
        from services.memory.research_memory import ResearchMemory
        mem = ResearchMemory()
        mem_ctx = mem.format_memory_context(state.get("memory_context",[]))
        result = hyp_gen.generate(
            literature_summary=state.get("literature_summary",""),
            graph_gaps=state.get("_graph_gaps",[]),
            influential_papers=state.get("influential_papers",[]),
            key_papers=state.get("key_papers",[]),
            memory_context=mem_ctx,
            query=state.get("query",""))  # pass query for fallback
        standard_hyps = result.get("hypotheses",[])
        cp_hyps = reasoner.combinations_to_hypotheses(state.get("cross_paper_combinations",[]))
        all_hyps = standard_hyps + cp_hyps
        logger.info(f"[Hypothesis] {len(standard_hyps)} standard + {len(cp_hyps)} cross-paper")
        return {**state, "raw_hypotheses":all_hyps, "hypotheses":all_hyps,
                "research_gaps":result.get("research_gaps",[]),
                "trends":result.get("trends",{}), "stage":"hypotheses_generated"}
    return hypothesize

def make_arena_node(arena):
    def score_arena(state):
        hyps = state.get("raw_hypotheses",[])
        domain = state.get("domain", state.get("query",""))
        result = arena.score_and_rank(hyps, domain)
        ranked = result.get("ranked",[])
        portfolio = result.get("top_portfolio",[])
        from core import metrics
        metrics.inc("arena_scored", len(ranked))
        top_for_debate = portfolio if portfolio else ranked[:5]
        return {**state, "arena_ranked":ranked, "top_portfolio":portfolio,
                "arena_stats":result.get("arena_stats",{}),
                "hypotheses":top_for_debate, "stage":"arena_scored"}
    return score_arena

def make_panel_node(panel, memory):
    def run_panel(state):
        from services.memory.research_memory import ResearchMemory
        mem = ResearchMemory()
        mem_ctx = mem.format_memory_context(state.get("memory_context",[]))
        result = panel.run_panel(
            hypotheses=state.get("hypotheses",[]),
            literature_summary=state.get("literature_summary",""),
            memory_context=mem_ctx)
        return {**state, "hypotheses":result.get("hypotheses",[]),
                "debate_transcript":result.get("debate_transcript",""), "stage":"panel_done"}
    return run_panel

def make_design_node(designer):
    def design(state):
        plans = designer.design_experiments(
            state.get("hypotheses",[]), state.get("domain", state.get("query","")))
        return {**state, "experiment_plans":plans, "stage":"experiments_designed"}
    return design

def make_warehouse_register_node(warehouse):
    def register(state):
        plans = state.get("experiment_plans",[])
        hyp_map = {h.get("id",""):h for h in state.get("hypotheses",[])}
        node_ids = {}
        for plan in plans:
            hyp = hyp_map.get(plan.get("hypothesis_id",""),{})
            nid = warehouse.add_experiment(
                experiment_id=plan.get("experiment_id",""),
                title=plan.get("title",""),
                hypothesis=hyp.get("statement", plan.get("hypothesis","")),
                domain=state.get("domain", state.get("query","")),
                source=hyp.get("source","standard"),
                depth=state.get("loop_iteration",0),
                scientist_score=float(hyp.get("scientist_score",0) or 0))
            node_ids[plan.get("experiment_id","")] = nid
        return {**state, "warehouse_node_ids":node_ids, "stage":"warehouse_registered"}
    return register

def make_run_node(runner):
    def run(state):
        plans = state.get("experiment_plans",[])
        if not plans or not state.get("run_experiments",True):
            return {**state, "experiment_results":[], "stage":"run_skipped"}
        results = runner.run_all(plans)
        errors = [r.get("error","") for r in results if r.get("status")=="error"]
        return {**state, "experiment_results":results, "execution_errors":errors, "stage":"run_done"}
    return run

def make_analyze_node(analyzer, memory, warehouse):
    def analyze(state):
        analysis = analyzer.analyze(
            experiment_results=state.get("experiment_results",[]),
            experiment_plans=state.get("experiment_plans",[]),
            hypotheses=state.get("hypotheses",[]),
            domain=state.get("domain", state.get("query","")))
        hyp_map = {h.get("id",""):h for h in state.get("hypotheses",[])}
        node_ids = state.get("warehouse_node_ids",{})
        for a in analysis.get("analyses",[]):
            exp_id = a.get("experiment_id","")
            plan = next((p for p in state.get("experiment_plans",[]) if p.get("experiment_id")==exp_id), {})
            hyp = hyp_map.get(plan.get("hypothesis_id",""),{})
            if hyp.get("statement"):
                mem_id = memory.add_hypothesis(hypothesis=hyp.get("statement",""),
                    domain=state.get("domain", state.get("query","")),
                    novelty_score=hyp.get("novelty_score",0),
                    feasibility_score=hyp.get("feasibility_score",0),
                    loop_iteration=state.get("loop_iteration",0))
                memory.update_result(mem_id,
                    status=a.get("hypothesis_verdict","inconclusive"),
                    result_summary=a.get("key_finding",""),
                    failure_reason=a.get("verdict_reasoning","") if a.get("hypothesis_verdict")=="rejected" else "",
                    metrics_dict=a.get("metrics",{}),
                    confidence_after=float(a.get("confidence_after_debate",0) or 0),
                    experiment_id=exp_id)
            nid = node_ids.get(exp_id,"")
            if nid:
                warehouse.update_result(nid,
                    status=a.get("hypothesis_verdict","inconclusive"),
                    metrics=a.get("metrics",{}),
                    failure_reason=a.get("verdict_reasoning","") if a.get("hypothesis_verdict")=="rejected" else "",
                    key_finding=a.get("key_finding",""),
                    hypothesis_verdict=a.get("hypothesis_verdict",""))
        return {**state, "analysis":analysis, "stage":"analyzed"}
    return analyze

def make_twin_node(twin, persona_name="Andrej Karpathy"):
    def twin_generate(state):
        if persona_name not in twin.list_personas():
            twin.load_famous_persona(persona_name)
        result = twin.generate_twin_hypothesis(persona_name, state.get("query",""), state.get("research_gaps",[]))
        return {**state, "twin_persona":result.get("twin_persona",""),
                "twin_hypothesis":result.get("twin_hypothesis",""), "stage":"twin_done"}
    return twin_generate

def make_loop_controller(memory):
    def loop_control(state):
        iteration = state.get("loop_iteration",0)
        if not config.AUTO_LOOP_ENABLED or iteration >= config.MAX_LOOP_ITERATIONS - 1:
            return {**state, "loop_should_continue":False}
        analysis = state.get("analysis",{})
        if not analysis.get("analyses"):
            return {**state, "loop_should_continue":False}
        llm = get_llm(temperature=0.1)
        summary = f"Iteration {iteration+1}/{config.MAX_LOOP_ITERATIONS}. {analysis.get('overall_insight','')}"
        resp = llm.invoke([SystemMessage(content=LOOP_PROMPT), HumanMessage(content=summary)])
        try:
            decision = json.loads(resp.content.strip().replace("```json","").replace("```",""))
        except: decision = {"continue":False}
        history = list(state.get("loop_history",[]))
        history.append({"iteration":iteration+1, "summary":analysis.get("overall_insight",""),
                         "next_focus":decision.get("next_focus","")})
        return {**state, "loop_should_continue":decision.get("continue",False),
                "loop_iteration":iteration+1, "loop_history":history,
                "query":decision.get("next_focus", state.get("query","")),
                "stage":"loop_evaluated"}
    return loop_control

def make_report_node(report_gen):
    def report(state):
        result = report_gen.generate(state)
        return {**state, "final_report":result["final_report"],
                "report_path":result["report_path"], "stage":"complete"}
    return report
