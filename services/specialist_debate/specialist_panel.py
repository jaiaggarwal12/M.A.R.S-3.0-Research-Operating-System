"""
Specialist Debate Panel — The Realistic Upgrade

Instead of generic Scientist/Skeptic/Reviewer,
this panel has domain-specific expertise:

  Theorist       — Does this have theoretical backing?
  Engineer       — Can this actually be implemented?
  Statistician   — Is the experimental design sound?
  Reviewer       — Would this get into NeurIPS/ICML?

The Statistician is the key addition. It rejects:
  - "p-value too weak"
  - "sample size insufficient for this claim"
  - "missing ablation studies"
  - "baseline comparison unfair"

This is how real ML papers get rejected, and how MARS learns
to generate better experiments.
"""
from __future__ import annotations
import json
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import get_llm
from core.logger import logger
from core import metrics


THEORIST_PROMPT = """You are a theoretical ML researcher.
Evaluate this hypothesis from a theoretical perspective:
1. Is there mathematical/theoretical justification for why this should work?
2. Does it contradict known theoretical results?
3. What theoretical framework would explain the expected improvement?
4. What are the theoretical failure modes?

Be precise. Reference relevant theory (PAC learning, information theory, optimisation theory). 
2-3 paragraphs."""

ENGINEER_PROMPT = """You are a senior ML engineer who has shipped models to production.
Evaluate this hypothesis from an implementation perspective:
1. What's the actual implementation complexity? (hours / days / weeks)
2. What are the most likely runtime errors or numerical issues?
3. Memory and compute requirements — is this realistic on a T4/A100?
4. What existing codebases/libraries make this easiest to implement?
5. What's the minimum viable experiment to test the core claim?

Be specific. Name actual libraries and estimated GPU memory. 2-3 paragraphs."""

STATISTICIAN_PROMPT = """You are a rigorous statistician reviewing an ML experiment design.
Evaluate the experimental validity:

MANDATORY CHECKS (fail any that are violated):
1. Sample size: Is n large enough to detect the claimed effect size?
2. Statistical significance: How many seeds/runs needed?
3. Baseline fairness: Are baselines tuned equally?
4. Ablation completeness: Which ablations are REQUIRED to isolate the contribution?
5. Evaluation metrics: Are the chosen metrics appropriate for the claim?
6. Dataset split: Is there data leakage risk?
7. Compute fairness: Are comparisons matched on FLOPs or parameters?

For each violated check, state: "REJECT: [reason]"
For passed checks, state: "PASS: [brief note]"

End with: VERDICT: ACCEPT | CONDITIONAL_ACCEPT | REJECT
If conditional: list exactly what must be fixed."""

REVIEWER_PROMPT = """You are a senior NeurIPS/ICML area chair.
Given the theoretical analysis, engineering assessment, and statistical review:

1. Novelty assessment: Is the contribution sufficiently novel for a top venue?
2. Significance: Would this paper change how people do things?
3. Completeness: What's missing for a full paper?
4. Likely review score: Strong Accept (8) / Accept (6) / Weak Accept (5) / Reject (3)
5. One specific change that would most improve the paper's chance of acceptance

Be direct. Reviewers don't give encouragement they don't mean."""

SYNTHESIS_PROMPT = """Given the specialist panel reviews, synthesise the final verdict.
Return JSON:
{
  "final_verdict": "go|conditional|no-go",
  "confidence": 1-10,
  "theorist_summary": "one sentence",
  "engineer_summary": "one sentence",
  "statistician_verdict": "ACCEPT|CONDITIONAL_ACCEPT|REJECT",
  "statistician_required_fixes": ["fix1", "fix2"],
  "reviewer_score": 3-8,
  "required_ablations": ["ablation1", "ablation2"],
  "required_baselines": ["baseline1"],
  "minimum_n_seeds": 3,
  "estimated_paper_venue": "NeurIPS|ICML|ICLR|workshop|arXiv",
  "panel_summary": "2-sentence summary of panel consensus",
  "refined_hypothesis": "improved statement after panel feedback"
}
Return ONLY valid JSON."""


class SpecialistPanel:
    """
    4-agent specialist review panel.
    More realistic than generic Scientist/Skeptic/Reviewer.
    """

    def run_panel(
        self,
        hypotheses: List[dict],
        literature_summary: str,
        memory_context: str,
    ) -> Dict:
        """
        Run specialist panel on top hypotheses.
        Returns refined hypotheses with panel verdicts.
        """
        refined = []
        transcripts = []
        total_panels = min(len(hypotheses), 3)

        for hyp in hypotheses[:total_panels]:
            logger.info(f"[SpecialistPanel] Panel review: {hyp.get('title','?')}")
            result = self._panel_one(hyp, literature_summary, memory_context)
            refined.append(result["refined"])
            transcripts.append(result["transcript"])

        metrics.inc("debate_rounds", total_panels)

        return {
            "hypotheses": refined,
            "debate_transcript": "\n\n" + ("=" * 60 + "\n\n").join(transcripts),
        }

    def _panel_one(self, hyp: dict, literature: str, memory: str) -> dict:
        llm = get_llm(temperature=0.3)

        hyp_ctx = (
            f"Hypothesis: {hyp.get('statement','')}\n"
            f"Motivation: {hyp.get('motivation','')}\n"
            f"Scientist Score: {hyp.get('scientist_score','?')}\n"
            f"Source: {hyp.get('source','standard')}\n"
            f"Related work: {', '.join(hyp.get('related_work',[])[:3])}"
        )
        full_ctx = f"{hyp_ctx}\n\nLiterature: {literature[:400]}\n\nMemory: {memory[:300]}"

        # Theorist
        theorist = llm.invoke([SystemMessage(content=THEORIST_PROMPT),
                                HumanMessage(content=full_ctx)]).content

        # Engineer
        engineer = llm.invoke([
            SystemMessage(content=ENGINEER_PROMPT),
            HumanMessage(content=f"{full_ctx}\n\nTheorist analysis:\n{theorist[:500]}"),
        ]).content

        # Statistician
        statistician = llm.invoke([
            SystemMessage(content=STATISTICIAN_PROMPT),
            HumanMessage(content=f"{full_ctx}\n\nProposed experiment:\n"
                         f"Metrics: {hyp.get('evaluation_metrics', hyp.get('metrics', []))}\n"
                         f"Baselines: {hyp.get('required_baselines', [])}"),
        ]).content

        # Reviewer
        reviewer = llm.invoke([
            SystemMessage(content=REVIEWER_PROMPT),
            HumanMessage(content=(
                f"{hyp_ctx}\n\n"
                f"Theorist: {theorist[:600]}\n\n"
                f"Engineer: {engineer[:600]}\n\n"
                f"Statistician: {statistician[:600]}"
            )),
        ]).content

        # Synthesis
        synth_resp = llm.invoke([
            SystemMessage(content=SYNTHESIS_PROMPT),
            HumanMessage(content=(
                f"Original: {hyp_ctx}\n\n"
                f"Theorist: {theorist[:400]}\n\n"
                f"Engineer: {engineer[:400]}\n\n"
                f"Statistician: {statistician[:400]}\n\n"
                f"Reviewer: {reviewer[:400]}"
            )),
        ]).content

        synth = self._parse_json(synth_resp)

        refined = {
            **hyp,
            "statement": synth.get("refined_hypothesis", hyp.get("statement", "")),
            "debate_verdict": synth.get("final_verdict", "conditional"),
            "verdict_reasoning": synth.get("panel_summary", ""),
            "required_ablations": synth.get("required_ablations", []),
            "required_baselines": synth.get("required_baselines", []),
            "statistician_verdict": synth.get("statistician_verdict", ""),
            "statistician_fixes": synth.get("statistician_required_fixes", []),
            "reviewer_score": synth.get("reviewer_score", 5),
            "estimated_venue": synth.get("estimated_paper_venue", "arXiv"),
            "minimum_seeds": synth.get("minimum_n_seeds", 3),
            "panel_confidence": synth.get("confidence", 5),
            "publishability": (
                "high" if synth.get("reviewer_score", 5) >= 6 else
                "medium" if synth.get("reviewer_score", 5) >= 5 else
                "low"
            ),
        }

        transcript = (
            f"## {hyp.get('title','?')}\n\n"
            f"### 🔮 Theorist\n{theorist}\n\n"
            f"### ⚙️  Engineer\n{engineer}\n\n"
            f"### 📊 Statistician\n{statistician}\n\n"
            f"### 📝 Reviewer\n{reviewer}\n\n"
            f"### ⚖️  Panel Verdict: {synth.get('final_verdict','?').upper()} "
            f"(Reviewer score: {synth.get('reviewer_score','?')}/8, "
            f"Venue: {synth.get('estimated_paper_venue','?')})\n"
            f"{synth.get('panel_summary','')}\n"
        )

        return {"refined": refined, "transcript": transcript}

    @staticmethod
    def _parse_json(raw: str) -> dict:
        raw = raw.strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("{"):
                    raw = part
                    break
        try:
            return json.loads(raw)
        except Exception:
            return {}
