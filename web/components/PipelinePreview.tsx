"use client";

import { motion } from "framer-motion";
import { PIPELINE } from "@/lib/pipeline";

export function PipelinePreview() {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-line bg-bg-soft p-8">
      <div className="absolute inset-0 grid-bg opacity-40" />
      <div className="relative">
        <div className="mb-6 flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-accent animate-pulse-glow" />
          <span className="text-xs font-medium uppercase tracking-widest text-faint">
            Autonomous Pipeline · 13 stages
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {PIPELINE.map((s, i) => {
            const Icon = s.icon;
            return (
              <motion.div
                key={s.id}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05, duration: 0.4 }}
                className="group flex items-center gap-2 rounded-xl border border-line bg-bg-card px-3 py-2 transition-colors hover:border-accent/50"
              >
                <Icon className="h-3.5 w-3.5 text-accent-soft" />
                <span className="text-xs font-medium text-muted group-hover:text-white">
                  {s.label}
                </span>
                {i < PIPELINE.length - 1 && (
                  <span className="ml-1 text-faint">→</span>
                )}
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
