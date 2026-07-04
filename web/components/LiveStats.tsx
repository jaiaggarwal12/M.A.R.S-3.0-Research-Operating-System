"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

const FALLBACK = {
  papers_indexed: 0,
  hypotheses_generated: 0,
  experiments_run: 0,
  graph_nodes: 0,
};

const ITEMS = [
  { key: "papers_indexed", label: "Papers Processed" },
  { key: "hypotheses_generated", label: "Hypotheses Generated" },
  { key: "experiments_run", label: "Experiments Designed" },
  { key: "graph_nodes", label: "Citation Nodes" },
];

export function LiveStats() {
  const [m, setM] = useState<Record<string, number>>(FALLBACK);

  useEffect(() => {
    api
      .metrics()
      .then((d) => setM(d as any))
      .catch(() => setM(FALLBACK));
  }, []);

  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-4">
      {ITEMS.map((it, i) => (
        <motion.div
          key={it.key}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 * i, duration: 0.5 }}
          className="bg-bg-card px-6 py-7 text-center"
        >
          <div className="text-3xl font-bold tracking-tight md:text-4xl">
            {formatNumber(m[it.key] ?? 0)}
          </div>
          <div className="mt-1.5 text-xs font-medium uppercase tracking-wider text-faint">
            {it.label}
          </div>
        </motion.div>
      ))}
    </div>
  );
}
