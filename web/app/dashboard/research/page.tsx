"use client";

import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, ArrowRight, AlertCircle } from "lucide-react";
import { api, type ResearchResult } from "@/lib/api";
import { PIPELINE } from "@/lib/pipeline";
import { LivePipeline } from "@/components/LivePipeline";
import { ReportReader } from "@/components/ReportReader";

const SUGGESTED = [
  "speculative decoding for LLM inference efficiency",
  "knowledge distillation in large language models",
  "retrieval augmented generation limitations",
  "graph neural networks for drug discovery",
];

const TWINS = ["Andrej Karpathy", "Andrew Ng", "Yann LeCun"];

export default function ResearchPage() {
  const [query, setQuery] = useState("");
  const [twin, setTwin] = useState(TWINS[0]);
  const [runExp, setRunExp] = useState(true);
  const [running, setRunning] = useState(false);
  const [active, setActive] = useState(-1);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [error, setError] = useState("");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const animateStages = () => {
    setActive(0);
    let i = 0;
    // ~150s total run → advance through stages steadily, hold on last few
    timer.current = setInterval(() => {
      i += 1;
      if (i < PIPELINE.length - 1) setActive(i);
      else if (timer.current) clearInterval(timer.current);
    }, 9000);
  };

  const run = async () => {
    if (!query.trim() || running) return;
    setRunning(true);
    setError("");
    setResult(null);
    animateStages();
    try {
      const res = await api.research({
        query: query.trim(),
        run_experiments: runExp,
        twin_persona: twin,
      });
      setResult(res);
      setActive(PIPELINE.length); // all done
    } catch (e: any) {
      setError(e.message || "Something went wrong");
      setActive(-1);
    } finally {
      if (timer.current) clearInterval(timer.current);
      setRunning(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      {/* command interface */}
      <AnimatePresence>
        {!running && !result && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mx-auto max-w-3xl pt-8 text-center"
          >
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-bg-card px-4 py-1.5 text-xs font-medium text-muted">
              <Sparkles className="h-3.5 w-3.5 text-accent-soft" />
              Autonomous research engine
            </div>
            <h1 className="text-4xl font-bold tracking-tight md:text-5xl">
              What would you like to
              <br />
              <span className="accent-text">investigate?</span>
            </h1>

            <div className="mt-8 rounded-2xl border border-line bg-bg-card p-2 transition-colors focus-within:border-accent/50">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run();
                }}
                rows={3}
                placeholder="What scientific question would you like to investigate?"
                className="w-full resize-none bg-transparent px-4 py-3 text-base text-white placeholder:text-faint focus:outline-none"
              />
              <div className="flex items-center justify-between gap-3 border-t border-line px-3 pt-3">
                <div className="flex items-center gap-3">
                  <select
                    value={twin}
                    onChange={(e) => setTwin(e.target.value)}
                    className="rounded-lg border border-line bg-bg-elevated px-3 py-1.5 text-xs text-muted focus:outline-none"
                  >
                    {TWINS.map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-muted">
                    <input
                      type="checkbox"
                      checked={runExp}
                      onChange={(e) => setRunExp(e.target.checked)}
                      className="accent-accent"
                    />
                    Run experiments
                  </label>
                </div>
                <button onClick={run} className="btn-primary">
                  Run Research OS <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              {SUGGESTED.map((s) => (
                <button
                  key={s}
                  onClick={() => setQuery(s)}
                  className="rounded-full border border-line bg-bg-card px-3.5 py-1.5 text-xs text-muted transition-colors hover:border-accent/40 hover:text-white"
                >
                  {s}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <div className="mx-auto mt-6 flex max-w-2xl items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* running / results */}
      {(running || result) && (
        <div className="mt-4">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-widest text-faint">
                Query
              </div>
              <h2 className="mt-1 text-xl font-semibold">{query}</h2>
            </div>
            {result && (
              <button
                onClick={() => {
                  setResult(null);
                  setActive(-1);
                  setQuery("");
                }}
                className="btn-ghost"
              >
                New query
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
            <LivePipeline activeIndex={active} />
            <div>
              {result ? (
                <ReportReader result={result} />
              ) : (
                <div className="card flex h-full min-h-[400px] flex-col items-center justify-center p-8 text-center">
                  <div className="skeleton mb-4 h-3 w-40" />
                  <div className="skeleton mb-2 h-3 w-64" />
                  <div className="skeleton h-3 w-52" />
                  <p className="mt-6 max-w-xs text-sm text-faint">
                    Running the full 13-stage pipeline. This takes ~2–3 minutes
                    on the free tier — the report appears here when complete.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
