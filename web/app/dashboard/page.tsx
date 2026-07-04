"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  FileText,
  FlaskConical,
  Lightbulb,
  Network,
  Trophy,
  Activity,
} from "lucide-react";
import { api, type Metrics } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

const STAT_CARDS = [
  { key: "papers_indexed", label: "Papers Indexed", icon: FileText },
  { key: "graph_nodes", label: "Graph Nodes", icon: Network },
  { key: "hypotheses_generated", label: "Hypotheses", icon: Lightbulb },
  { key: "experiments_run", label: "Experiments Run", icon: FlaskConical },
  { key: "arena_scored", label: "Arena Scored", icon: Trophy },
  { key: "successful_discoveries", label: "Discoveries", icon: Activity },
];

export default function CommandCenter() {
  const [m, setM] = useState<Metrics | null>(null);
  const [status, setStatus] = useState<"ok" | "waking" | "down">("waking");

  useEffect(() => {
    api
      .metrics()
      .then((d) => {
        setM(d);
        setStatus("ok");
      })
      .catch(() => setStatus("down"));
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-10 flex items-end justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-faint">
            <span
              className={
                "h-2 w-2 rounded-full " +
                (status === "ok"
                  ? "bg-emerald-400"
                  : status === "waking"
                  ? "bg-amber-400 animate-pulse"
                  : "bg-red-400")
              }
            />
            {status === "ok"
              ? "System online"
              : status === "waking"
              ? "Connecting…"
              : "Backend waking (free tier ~30s)"}
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Command Center</h1>
        </div>
        <Link href="/dashboard/research" className="btn-primary">
          New Research <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      {/* stat grid */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        {STAT_CARDS.map((c, i) => {
          const Icon = c.icon;
          return (
            <motion.div
              key={c.key}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06, duration: 0.5 }}
              className="card card-hover p-6"
            >
              <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-bg-elevated">
                <Icon className="h-4 w-4 text-accent-soft" />
              </div>
              <div className="text-3xl font-bold tracking-tight">
                {m ? formatNumber(m[c.key] ?? 0) : "—"}
              </div>
              <div className="mt-1 text-sm text-faint">{c.label}</div>
            </motion.div>
          );
        })}
      </div>

      {/* feature row */}
      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Link
          href="/dashboard/research"
          className="card card-hover group col-span-2 flex flex-col justify-between p-7"
        >
          <div>
            <FlaskConical className="mb-4 h-6 w-6 text-accent-soft" />
            <h3 className="text-xl font-semibold">Run a full research cycle</h3>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">
              Submit a scientific question and watch the 13-stage pipeline
              execute live — retrieval, synthesis, hypotheses, expert panel,
              experiments, and a publication-ready report.
            </p>
          </div>
          <div className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-accent-soft group-hover:gap-3 transition-all">
            Start research <ArrowRight className="h-4 w-4" />
          </div>
        </Link>

        <Link
          href="/dashboard/arena"
          className="card card-hover group flex flex-col justify-between p-7"
        >
          <div>
            <Trophy className="mb-4 h-6 w-6 text-accent-soft" />
            <h3 className="text-lg font-semibold">Arena Leaderboard</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              Ranked hypotheses across all sessions.
            </p>
          </div>
          <div className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-accent-soft group-hover:gap-3 transition-all">
            View arena <ArrowRight className="h-4 w-4" />
          </div>
        </Link>
      </div>
    </div>
  );
}
