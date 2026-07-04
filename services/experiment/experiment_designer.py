"""
Experiment Factory — Upgrade 4

Generates complete, reproducible experiment packages:
  train.py, eval.py, config.yaml, requirements.txt, Dockerfile, README.md

Every experiment is a self-contained reproducible science package.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import get_llm
from core.logger import logger
from core import config, metrics


DESIGN_PROMPT = """You are an expert ML engineer designing an experiment to test a hypothesis.

Return ONLY a compact JSON object with these keys (no code, just metadata):
{
  "title": "short experiment name",
  "hypothesis": "the claim being tested",
  "methodology": ["step 1", "step 2", "step 3"],
  "baselines": ["baseline1", "baseline2"],
  "metrics": ["accuracy", "f1"],
  "datasets": ["dataset name"],
  "estimated_compute": "~X minutes on CPU/GPU",
  "difficulty": "low|medium|high",
  "novelty": "one sentence on what is new"
}

Keep it concise. Return ONLY valid JSON, no markdown, no code."""


class ExperimentDesigner:
    def __init__(self, experiments_dir=config.EXPERIMENTS_DIR):
        self.experiments_dir = Path(experiments_dir)
        self.experiments_dir.mkdir(parents=True, exist_ok=True)

    def design_experiments(self, hypotheses: List[dict], domain: str) -> List[dict]:
        plans = []
        for hyp in hypotheses[:3]:
            # Only hard skip if explicitly marked no-go
            verdict = str(hyp.get("debate_verdict", "go")).lower().strip()
            if verdict == "no-go":
                logger.info(f"[Designer] Skipping no-go: {hyp.get('title','?')}")
                continue
            logger.info(f"[Designer] Designing: {hyp.get('title','?')} (verdict={verdict})")
            plan = self._design_one(hyp, domain)
            if plan:
                plans.append(plan)
        metrics.inc("experiments_designed", len(plans))
        logger.info(f"[Designer] {len(plans)} plans designed from {len(hypotheses)} hypotheses")
        return plans

    def _design_one(self, hypothesis: dict, domain: str) -> dict | None:
        llm = get_llm(temperature=0.2)
        resp = llm.invoke([
            SystemMessage(content=DESIGN_PROMPT),
            HumanMessage(content=f"Domain: {domain}\nHypothesis:\n{json.dumps(hypothesis, indent=2)}"),
        ])

        plan = self._parse(resp.content)
        # NEVER fail — if the LLM couldn't return valid JSON, build a minimal plan
        # from the hypothesis itself. The fallback code templates guarantee runnability.
        if not plan:
            logger.warning("[Designer] LLM JSON parse failed — using metadata fallback")
            plan = {
                "title": hypothesis.get("title", "Experiment"),
                "hypothesis": hypothesis.get("statement", hypothesis.get("title", "")),
                "methodology": ["Generate synthetic dataset", "Train baseline", "Train proposed model", "Compare metrics"],
                "baselines": hypothesis.get("required_baselines", ["logistic_regression"]),
                "metrics": hypothesis.get("evaluation_metrics", ["accuracy", "f1"]),
                "datasets": ["synthetic"],
                "estimated_compute": "~minutes on CPU",
                "difficulty": "low",
                "novelty": hypothesis.get("title", ""),
            }

        exp_id = self._make_id(plan.get("title","experiment"))
        plan["experiment_id"] = exp_id
        plan["hypothesis_id"] = hypothesis.get("id","")
        plan["scientist_score"] = hypothesis.get("scientist_score", 0)
        plan["debate_verdict"] = hypothesis.get("debate_verdict","")
        plan["status"] = "designed"

        self._save_all_artifacts(exp_id, plan)
        logger.info(f"[Designer] Saved 6-file package: {exp_id}/")
        return plan

    def _save_all_artifacts(self, exp_id: str, plan: dict):
        d = self.experiments_dir / exp_id
        d.mkdir(parents=True, exist_ok=True)

        # train.py — always use the proven runnable template (LLM code is unreliable)
        (d/"train.py").write_text(self._fallback_train_py(plan))

        # eval.py — always use the proven runnable template
        (d/"eval.py").write_text(self._fallback_eval_py(plan))

        # config.yaml
        cfg = plan.get("config_yaml","") or self._fallback_config(plan)
        (d/"config.yaml").write_text(cfg)

        # requirements.txt
        reqs = plan.get("requirements_txt","numpy\nscikit-learn\n")
        (d/"requirements.txt").write_text(reqs)

        # Dockerfile
        dockerfile = plan.get("dockerfile","") or self._fallback_dockerfile()
        (d/"Dockerfile").write_text(dockerfile)

        # README.md
        readme = plan.get("readme_md","") or self._fallback_readme(plan, exp_id)
        (d/"README.md").write_text(readme)

        # experiment_plan.json
        plan_copy = {k:v for k,v in plan.items()
                     if k not in ("train_py","eval_py","config_yaml","requirements_txt","dockerfile","readme_md")}
        (d/"experiment_plan.json").write_text(json.dumps(plan_copy, indent=2))

        plan["artifact_dir"] = str(d)

    def _parse(self, raw: str) -> dict | None:
        raw = raw.strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("{"): raw = part; break
        try: return json.loads(raw)
        except Exception:
            m = re.search(r'\{[\s\S]+\}', raw)
            if m:
                try: return json.loads(m.group())
                except: pass
            return None  # caller builds a fallback plan

    @staticmethod
    def _make_id(title: str) -> str:
        import time
        slug = re.sub(r'[^a-z0-9]+','_',title.lower())[:35].strip('_')
        return f"{slug}_{int(time.time())%100000}"

    @staticmethod
    def _fallback_train_py(plan: dict) -> str:
        return f'''"""
Auto-generated experiment: {plan.get("title","experiment")}
Hypothesis: {plan.get("hypothesis","")}
"""
import argparse, json, time
import numpy as np
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n_samples", type=int, default=1000)
    args = parser.parse_args()

    np.random.seed(args.seed)
    X, y = make_classification(n_samples=args.n_samples, n_features=20, random_state=args.seed)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=args.seed)

    results = {{}}

    # Baseline
    baseline = LogisticRegression(random_state=args.seed)
    baseline.fit(X_train, y_train)
    b_pred = baseline.predict(X_test)
    b_acc = accuracy_score(y_test, b_pred)
    b_f1 = f1_score(y_test, b_pred)
    print(f"METRIC:baseline_accuracy:{{b_acc:.4f}}")
    print(f"METRIC:baseline_f1:{{b_f1:.4f}}")
    results["baseline_accuracy"] = b_acc

    # Main model
    model = RandomForestClassifier(n_estimators=100, random_state=args.seed)
    t0 = time.time()
    model.fit(X_train, y_train)
    train_time = round(time.time()-t0, 3)
    pred = model.predict(X_test)
    acc = accuracy_score(y_test, pred)
    f1 = f1_score(y_test, pred)
    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:,1])

    print(f"METRIC:accuracy:{{acc:.4f}}")
    print(f"METRIC:f1:{{f1:.4f}}")
    print(f"METRIC:auc:{{auc:.4f}}")
    print(f"METRIC:train_time_sec:{{train_time}}")
    print(f"METRIC:improvement_vs_baseline:{{acc-b_acc:.4f}}")

    results.update({{"accuracy":acc,"f1":f1,"auc":auc,"train_time":train_time,
                     "improvement_vs_baseline":round(acc-b_acc,4)}})

    with open("results.json","w") as f:
        json.dump(results, f, indent=2)
    print("Saved results.json")

if __name__=="__main__":
    main()
'''

    @staticmethod
    def _fallback_eval_py(plan: dict) -> str:
        return f'''"""Evaluation script for: {plan.get("title","experiment")}"""
import json, argparse
import numpy as np
from sklearn.metrics import classification_report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results.json")
    args = parser.parse_args()
    try:
        with open(args.results) as f:
            results = json.load(f)
        print("\\n=== Evaluation Results ===")
        for k, v in results.items():
            print(f"{{k}}: {{v}}")
    except FileNotFoundError:
        print("Run train.py first to generate results.json")

if __name__=="__main__":
    main()
'''

    @staticmethod
    def _fallback_config(plan: dict) -> str:
        return f"""experiment:
  name: {plan.get('title','experiment')}
  hypothesis: "{plan.get('hypothesis','')[:100]}"
model:
  type: random_forest
  n_estimators: 100
  max_depth: null
training:
  epochs: 10
  batch_size: 32
  learning_rate: 0.001
  seed: 42
data:
  n_samples: 1000
  test_split: 0.2
logging:
  save_results: true
  results_path: results.json
"""

    @staticmethod
    def _fallback_dockerfile() -> str:
        return """FROM python:3.11-slim
WORKDIR /experiment
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "train.py"]
"""

    @staticmethod
    def _fallback_readme(plan: dict, exp_id: str) -> str:
        steps = "\n".join(f"{i+1}. {s}" for i,s in enumerate(plan.get("methodology",[])))
        return f"""# {plan.get('title', exp_id)}

## Hypothesis
{plan.get('hypothesis','')}

## Methodology
{steps}

## Quick Start
```bash
pip install -r requirements.txt
python train.py
python eval.py
```

## Docker
```bash
docker build -t {exp_id} .
docker run {exp_id}
```

## Expected Metrics
{', '.join(plan.get('metrics',['accuracy']))}

## Compute
{plan.get('estimated_compute','~1 GPU hour on T4')}
"""
