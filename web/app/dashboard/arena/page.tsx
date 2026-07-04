"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";
import { Trophy, Medal } from "lucide-react";
import { api } from "@/lib/api";

export default function ArenaPage() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState<any>(null);

  useEffect(() => {
    api
      .arena()
      .then((d) => {
        setData(d);
        setSel(d.entries?.[0] || null);
      })
      .catch((e) => setErr(e.message));
  }, []);

  const radarData = sel
    ? [
        { k: "Novelty", v: sel.novelty_score || 0 },
        { k: "Impact", v: sel.expected_impact || 0 },
        { k: "Feasibility", v: sel.feasibility_score || 0 },
        { k: "Low Risk", v: 10 - (sel.risk_score || 0) },
        { k: "Score", v: sel.scientist_score || 0 },
      ]
    : [];

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-8 flex items-center gap-3">
        <Trophy className="h-6 w-6 text-accent-soft" />
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Arena</h1>
          <p className="text-sm text-faint">
            Ranked hypothesis leaderboard across all research sessions.
          </p>
        </div>
      </div>

      {err && <p className="text-sm text-red-400">{err}</p>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
        {/* leaderboard */}
        <div className="space-y-2.5">
          {data?.entries?.length ? (
            data.entries.map((e: any, i: number) => (
              <motion.button
                key={e.id || i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                onClick={() => setSel(e)}
                className={
                  "card w-full p-4 text-left transition-all " +
                  (sel?.id === e.id
                    ? "border-accent/50 bg-bg-elevated"
                    : "card-hover")
                }
              >
                <div className="flex items-center gap-4">
                  <div
                    className={
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-bold " +
                      (i < 3
                        ? "bg-accent-gradient text-white"
                        : "border border-line text-faint")
                    }
                  >
                    {i < 3 ? <Medal className="h-4 w-4" /> : i + 1}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-white">
                      {e.title}
                    </div>
                    <div className="mt-1.5 flex gap-3 text-xs text-faint">
                      <span>N {e.novelty_score}</span>
                      <span>I {e.expected_impact}</span>
                      <span>F {e.feasibility_score}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold accent-text">
                      {Number(e.scientist_score).toFixed(1)}
                    </div>
                    <div className="text-[10px] uppercase tracking-wider text-faint">
                      score
                    </div>
                  </div>
                </div>
              </motion.button>
            ))
          ) : (
            <div className="card p-10 text-center text-sm text-faint">
              No ranked hypotheses yet. Run a research query first.
            </div>
          )}
        </div>

        {/* radar detail */}
        {sel && (
          <div className="card h-fit p-5">
            <div className="mb-1 text-xs uppercase tracking-widest text-faint">
              Profile
            </div>
            <div className="mb-4 text-sm font-semibold">{sel.title}</div>
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#1e1e26" />
                <PolarAngleAxis
                  dataKey="k"
                  tick={{ fill: "#8a8a99", fontSize: 11 }}
                />
                <Radar
                  dataKey="v"
                  stroke="#7c5cff"
                  fill="#7c5cff"
                  fillOpacity={0.3}
                />
              </RadarChart>
            </ResponsiveContainer>
            {sel.one_line_pitch && (
              <p className="mt-3 text-xs italic text-muted">
                “{sel.one_line_pitch}”
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
