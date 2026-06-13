from __future__ import annotations
import json, os, re, subprocess, time
from pathlib import Path
from typing import Dict, List
from core.logger import logger
from core import config, metrics

METRIC_RE = re.compile(r'METRIC:([^:]+):(.+)')

class ExperimentRunner:
    def __init__(self, mode=config.EXPERIMENT_RUNNER, timeout=config.EXPERIMENT_TIMEOUT):
        self.mode = mode
        self.timeout = timeout

    def run_all(self, plans: List[dict]) -> List[dict]:
        return [self.run_one(p) for p in plans]

    def run_one(self, plan: dict) -> dict:
        exp_id = plan.get("experiment_id","unknown")
        adir = plan.get("artifact_dir","")
        if not adir or not Path(adir).exists():
            return self._err(exp_id, "Artifact dir not found")
        train_py = Path(adir)/"train.py"
        if not train_py.exists():
            return self._err(exp_id, "train.py not found")

        logger.info(f"[Runner] {exp_id} (mode={self.mode})")
        t0 = time.perf_counter()

        try:
            r = self._run_local(exp_id, adir, str(train_py)) if self.mode != "docker" else self._run_docker(exp_id, adir)
        except Exception as exc:
            r = self._err(exp_id, str(exc))

        r["elapsed_sec"] = round(time.perf_counter()-t0, 2)
        r["experiment_id"] = exp_id
        r["title"] = plan.get("title", exp_id)

        success = r.get("status") == "success"
        metrics.record_experiment(success)

        if adir:
            (Path(adir)/"run_results.json").write_text(json.dumps(r, indent=2))
        return r

    def _run_local(self, exp_id, adir, train_py) -> dict:
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent.parent)}
        try:
            proc = subprocess.run(
                ["python", train_py],
                capture_output=True, text=True,
                timeout=self.timeout, cwd=adir, env=env)
            parsed = self._parse_metrics(proc.stdout)
            return {
                "status": "success" if proc.returncode==0 else "failed",
                "returncode": proc.returncode,
                "stdout": proc.stdout[-3000:],
                "stderr": proc.stderr[-1000:],
                "parsed_metrics": parsed,
                "results_json": self._load_results(adir),
            }
        except subprocess.TimeoutExpired:
            return self._err(exp_id, f"Timeout after {self.timeout}s")

    def _run_docker(self, exp_id, adir) -> dict:
        try:
            import docker
            client = docker.from_env()
            out = client.containers.run(
                "python:3.11-slim",
                command="bash -c 'pip install -r /exp/requirements.txt -q && python /exp/train.py'",
                volumes={adir: {"bind":"/exp","mode":"rw"}},
                working_dir="/exp", mem_limit="2g",
                cpu_quota=50000, network_disabled=True, remove=True,
                stdout=True, stderr=True)
            output = out.decode() if isinstance(out, bytes) else str(out)
            return {"status":"success","returncode":0,"stdout":output[-3000:],"stderr":"",
                    "parsed_metrics":self._parse_metrics(output),"results_json":self._load_results(adir)}
        except Exception as exc:
            logger.warning(f"Docker failed, local fallback: {exc}")
            return self._run_local(exp_id, adir, str(Path(adir)/"train.py"))

    @staticmethod
    def _parse_metrics(stdout: str) -> dict:
        out = {}
        for line in stdout.splitlines():
            m = METRIC_RE.match(line.strip())
            if m:
                try: out[m.group(1).strip()] = float(m.group(2).strip())
                except: out[m.group(1).strip()] = m.group(2).strip()
        return out

    @staticmethod
    def _load_results(adir: str) -> dict:
        p = Path(adir)/"results.json"
        if p.exists():
            try: return json.loads(p.read_text())
            except: pass
        return {}

    @staticmethod
    def _err(exp_id, msg) -> dict:
        return {"experiment_id":exp_id,"status":"error","error":msg,
                "stdout":"","stderr":"","parsed_metrics":{},"results_json":{}}
