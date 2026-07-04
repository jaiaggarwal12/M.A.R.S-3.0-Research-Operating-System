"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Boxes, FileCode2 } from "lucide-react";
import { api } from "@/lib/api";

export default function WarehousePage() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.experiments().then(setData).catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-8 flex items-center gap-3">
        <Boxes className="h-6 w-6 text-accent-soft" />
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Warehouse</h1>
          <p className="text-sm text-faint">
            Every generated experiment package — reproducible 6-file science
            bundles.
          </p>
        </div>
      </div>

      {err && <p className="text-sm text-red-400">{err}</p>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {data?.experiments?.length ? (
          data.experiments.map((e: any, i: number) => (
            <motion.div
              key={e.experiment_id || i}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="card card-hover p-5"
            >
              <FileCode2 className="mb-3 h-5 w-5 text-accent-soft" />
              <div className="text-sm font-semibold text-white">
                {e.title || e.experiment_id}
              </div>
              <p className="mt-2 line-clamp-3 text-xs text-muted">
                {e.hypothesis || e.novelty || "Experiment package"}
              </p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {["train.py", "eval.py", "Dockerfile", "config.yaml"].map((f) => (
                  <span
                    key={f}
                    className="rounded-md border border-line px-2 py-0.5 text-[10px] text-faint"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </motion.div>
          ))
        ) : (
          <div className="card col-span-full p-10 text-center text-sm text-faint">
            No experiments generated yet. Run a research query first.
          </div>
        )}
      </div>
    </div>
  );
}
