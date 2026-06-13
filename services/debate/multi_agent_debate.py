"""
Multi-Agent Debate — Upgrade 2

Three agents debate each hypothesis before it becomes an experiment:

  Scientist Agent  — proposes and defends the hypothesis
  Skeptic Agent    — challenges assumptions, data, feasibility
  Reviewer Agent   — acts as peer reviewer, demands rigour

Output: refined hypothesis + debate transcript + go/no-go verdict.

This mirrors actual peer review and is extremely rare in student projects.
"""
from __future__ import annotations
import json
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import get_llm
from core.logger import logger
from core import metrics


SCIENTIST_PROMPT = """You are a confident ML researcher proposing a hypothesis.
Given the hypothesis and supporting evidence, make the strongest possible case for it.
Address: Why it's novel, why it should work, what evidence supports it.
Be specific and technical. 2-3 paragraphs."""

SKEPTIC_PROMPT = """You are a rigorous ML skeptic reviewing a research hypothesis.
Your job is to find weaknesses. Challenge:
- Is the dataset large enough?
- Has this been tried before (in disguise)?
- Are the compute requirements realistic for a student?
- What's the most likely failure mode?
- Is the baseline comparison fair?
Be specific. 2-3 sharp critiques."""

REVIEWER_PROMPT = """You are a senior NeurIPS/ICML reviewer evaluating this hypothesis for publication.
Given the scientist's defense and skeptic's critique, provide:
1. What ablation studies are required
2. What baselines must be included
3. What would make this publishable vs. not
4. Go / No-Go verdict with reasoning
Be precise. This is a paper review, not encouragement."""

SYNTHESIS_PROMPT = """Given this debate between a Scientist, Skeptic, and Reviewer about a research hypothesis,
synthesise the final refined hypothesis.

Return JSON:
{
  "refined_hypothesis": "improved statement incorporating feedback",
  "verdict": "go|no-go|conditional",
  "verdict_reasoning": "one sentence",
  "required_changes": ["change1", "change2"],
  "required_ablations": ["ablation1"],
  "required_baselines": ["baseline1"],
  "confidence_after_debate": 1-10,
  "publishability": "high|medium|low",
  "debate_summary": "2-sentence summary of key debate points"
}"""


class MultiAgentDebate:
    """
    Runs a 3-agent debate for each hypothesis.
    Returns refined hypotheses with verdicts.
    """

    def run_debates(
        self,
        hypotheses: List[dict],
        literature_summary: str,
        memory_context: str,
    ) -> Dict:
        """
        Debate all hypotheses. Returns:
          - debated_hypotheses: refined list
          - debate_transcripts: full transcripts
        """
        debated = []
        transcripts = []

        for hyp in hypotheses[:3]:   # Debate top 3 hypotheses
            logger.info(f"[Debate] Starting debate: {hyp.get('title','?')}")
            result = self._debate_one(hyp, literature_summary, memory_context)
            debated.append(result["refined"])
            transcripts.append(result["transcript"])

        metrics.inc("debate_rounds", len(debated))
        full_transcript = "\n\n" + ("="*60) + "\n\n".join(transcripts)
        return {"hypotheses": debated, "debate_transcript": full_transcript}

    def _debate_one(self, hypothesis: dict, literature: str, memory: str) -> dict:
        llm = get_llm(temperature=0.3)

        hyp_text = (
            f"Hypothesis: {hypothesis.get('statement','')}\n"
            f"Motivation: {hypothesis.get('motivation','')}\n"
            f"Novelty score: {hypothesis.get('novelty_score','?')}/10\n"
            f"Related work: {', '.join(hypothesis.get('related_work',[]))}"
        )

        context = (
            f"{hyp_text}\n\n"
            f"Literature context: {literature[:400]}\n\n"
            f"Prior experiments in memory:\n{memory}"
        )

        # Round 1: Scientist defends
        scientist_resp = llm.invoke([
            SystemMessage(content=SCIENTIST_PROMPT),
            HumanMessage(content=context),
        ]).content

        # Round 2: Skeptic attacks
        skeptic_resp = llm.invoke([
            SystemMessage(content=SKEPTIC_PROMPT),
            HumanMessage(content=f"{context}\n\nScientist's defense:\n{scientist_resp}"),
        ]).content

        # Round 3: Reviewer adjudicates
        reviewer_resp = llm.invoke([
            SystemMessage(content=REVIEWER_PROMPT),
            HumanMessage(content=(
                f"{context}\n\n"
                f"Scientist: {scientist_resp}\n\n"
                f"Skeptic: {skeptic_resp}"
            )),
        ]).content

        # Synthesis
        synthesis_resp = llm.invoke([
            SystemMessage(content=SYNTHESIS_PROMPT),
            HumanMessage(content=(
                f"Original hypothesis: {hyp_text}\n\n"
                f"Scientist: {scientist_resp}\n\n"
                f"Skeptic: {skeptic_resp}\n\n"
                f"Reviewer: {reviewer_resp}"
            )),
        ]).content

        synthesis = self._parse_json(synthesis_resp)

        # Build refined hypothesis
        refined = {
            **hypothesis,
            "statement": synthesis.get("refined_hypothesis", hypothesis.get("statement","")),
            "debate_verdict": synthesis.get("verdict", "conditional"),
            "verdict_reasoning": synthesis.get("verdict_reasoning",""),
            "required_ablations": synthesis.get("required_ablations",[]),
            "required_baselines": synthesis.get("required_baselines",[]),
            "confidence_after_debate": synthesis.get("confidence_after_debate", 5),
            "publishability": synthesis.get("publishability","medium"),
            "debate_summary": synthesis.get("debate_summary",""),
        }

        transcript = (
            f"## Hypothesis: {hypothesis.get('title','?')}\n\n"
            f"### 🔬 Scientist\n{scientist_resp}\n\n"
            f"### 🔍 Skeptic\n{skeptic_resp}\n\n"
            f"### 📋 Reviewer\n{reviewer_resp}\n\n"
            f"### ⚖️ Verdict: {synthesis.get('verdict','?').upper()}\n"
            f"{synthesis.get('verdict_reasoning','')}\n"
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
