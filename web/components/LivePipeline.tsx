"use client";

import { motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import { PIPELINE } from "@/lib/pipeline";
import { cn } from "@/lib/utils";

interface Props {
  activeIndex: number; // -1 = idle, >=PIPELINE.length = done
}

export function LivePipeline({ activeIndex }: Props) {
  return (
    <div className="card p-6">
      <div className="mb-5 flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full bg-accent animate-pulse-glow" />
        <span className="text-xs font-medium uppercase tracking-widest text-faint">
          Live Pipeline
        </span>
      </div>

      <div className="space-y-1.5">
        {PIPELINE.map((stage, i) => {
          const done = i < activeIndex;
          const active = i === activeIndex;
          const Icon = stage.icon;
          return (
            <div key={stage.id} className="relative">
              {i < PIPELINE.length - 1 && (
                <div
                  className={cn(
                    "absolute left-[19px] top-9 h-[calc(100%-8px)] w-px transition-colors duration-500",
                    done ? "bg-accent/50" : "bg-line"
                  )}
                />
              )}
              <motion.div
                initial={false}
                animate={{
                  backgroundColor: active
                    ? "rgba(124,92,255,0.08)"
                    : "rgba(0,0,0,0)",
                }}
                className="flex items-center gap-3 rounded-xl px-2 py-2"
              >
                <div
                  className={cn(
                    "relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition-all duration-300",
                    done
                      ? "border-accent/40 bg-accent/15 text-accent-soft"
                      : active
                      ? "border-accent bg-accent/20 text-white"
                      : "border-line bg-bg-elevated text-faint"
                  )}
                >
                  {done ? (
                    <Check className="h-4 w-4" />
                  ) : active ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                </div>
                <div className="min-w-0">
                  <div
                    className={cn(
                      "text-sm font-medium transition-colors",
                      done || active ? "text-white" : "text-faint"
                    )}
                  >
                    {stage.label}
                  </div>
                  <div className="truncate text-xs text-faint">
                    {stage.desc}
                  </div>
                </div>
                {active && (
                  <span className="ml-auto text-xs font-medium text-accent-soft">
                    running…
                  </span>
                )}
                {done && (
                  <span className="ml-auto text-xs font-medium text-emerald-400/70">
                    done
                  </span>
                )}
              </motion.div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
