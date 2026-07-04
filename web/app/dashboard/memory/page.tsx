"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Brain, CheckCircle2, XCircle, HelpCircle } from "lucide-react";
import { api } from "@/lib/api";

const ICON: Record<string, any> = {
  confirmed: CheckCircle2,
  success: CheckCircle2,
  rejected: XCircle,
  failed: XCircle,
};

export default function MemoryPage() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.memory().then(setData).catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <div className="mb-8 flex items-center gap-3">
        <Brain className="h-6 w-6 text-accent-soft" />
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Research Memory</h1>
          <p className="text-sm text-faint">
            Every hypothesis tried, its result, and failure reasons — persisted
            across sessions.
          </p>
        </div>
      </div>

      {data && (
        <div className="mb-6 flex gap-3">
          <Stat label="Total" value={data.total} />
          <Stat label="Confirmed" value={data.successful} tone="emerald" />
          <Stat label="Failed" value={data.failed} tone="red" />
        </div>
      )}

      {err && <p className="text-sm text-red-400">{err}</p>}

      <div className="space-y-3">
        {data?.entries?.length ? (
          data.entries.map((e: any, i: number) => {
            const Icon = ICON[e.status] || HelpCircle;
            return (
              <motion.div
                key={e.id || i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="card card-hover p-5"
              >
                <div className="flex items-start gap-3">
                  <Icon className="mt-0.5 h-5 w-5 shrink-0 text-accent-soft" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-white">
                      {e.hypothesis}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-faint">
                      <span className="rounded-md border border-line px-2 py-0.5">
                        {e.status}
                      </span>
                      <span className="rounded-md border border-line px-2 py-0.5">
                        loop {e.loop_iteration ?? 0}
                      </span>
                      {e.created_at && (
                        <span className="rounded-md border border-line px-2 py-0.5">
                          {String(e.created_at).slice(0, 10)}
                        </span>
                      )}
                    </div>
                    {e.result_summary && (
                      <p className="mt-2 text-sm text-muted">
                        {e.result_summary}
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })
        ) : (
          <div className="card p-10 text-center text-sm text-faint">
            No memory entries yet. Run a research query first.
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <div className="card flex-1 p-4 text-center">
      <div
        className={
          "text-2xl font-bold " +
          (tone === "emerald"
            ? "text-emerald-400"
            : tone === "red"
            ? "text-red-400"
            : "text-white")
        }
      >
        {value ?? 0}
      </div>
      <div className="text-xs text-faint">{label}</div>
    </div>
  );
}
