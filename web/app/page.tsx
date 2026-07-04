"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Play, Sparkles, Github } from "lucide-react";
import { BackgroundGraph } from "@/components/BackgroundGraph";
import { LiveStats } from "@/components/LiveStats";
import { PipelinePreview } from "@/components/PipelinePreview";

export default function Landing() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* ambient glow */}
      <div className="pointer-events-none absolute left-1/2 top-0 h-[600px] w-[900px] -translate-x-1/2 bg-grid-fade" />
      <BackgroundGraph />

      {/* nav */}
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-gradient text-sm font-bold">
            M
          </div>
          <span className="text-sm font-semibold tracking-tight">
            M.A.R.S <span className="text-faint">4.0</span>
          </span>
        </div>
        <nav className="flex items-center gap-3">
          <a
            href="https://github.com/jaiaggarwal12/M.A.R.S-3.0-Research-Operating-System"
            target="_blank"
            rel="noreferrer"
            className="btn-ghost hidden sm:inline-flex"
          >
            <Github className="h-4 w-4" /> GitHub
          </a>
          <Link href="/dashboard" className="btn-primary">
            Launch Research OS <ArrowRight className="h-4 w-4" />
          </Link>
        </nav>
      </header>

      {/* hero */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 pb-16 pt-20 text-center md:pt-28">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-line bg-bg-card/60 px-4 py-1.5 text-xs font-medium text-muted backdrop-blur"
        >
          <Sparkles className="h-3.5 w-3.5 text-accent-soft" />
          Not a chatbot — an operating system for science
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05 }}
          className="mx-auto max-w-4xl text-5xl font-extrabold leading-[1.05] tracking-tight md:text-7xl"
        >
          Autonomous Research
          <br />
          <span className="accent-text">Operating System</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15 }}
          className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted"
        >
          M.A.R.S 4.0 autonomously reads papers, builds knowledge graphs,
          synthesizes cross-paper ideas, generates hypotheses, runs a
          multi-agent expert panel, designs and executes experiments, and
          produces publication-ready research reports.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.25 }}
          className="mt-9 flex items-center justify-center gap-3"
        >
          <Link href="/dashboard" className="btn-primary px-6 py-3 text-base">
            Launch Research OS <ArrowRight className="h-4 w-4" />
          </Link>
          <Link href="/dashboard/research" className="btn-ghost px-6 py-3 text-base">
            <Play className="h-4 w-4" /> Watch it work
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="mx-auto mt-16 max-w-4xl"
        >
          <LiveStats />
        </motion.div>
      </section>

      {/* pipeline */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-24">
        <PipelinePreview />
      </section>

      <footer className="relative z-10 border-t border-line py-8 text-center text-xs text-faint">
        M.A.R.S 4.0 — Research Operating System · Powered by Groq · Llama 3.3 70B
      </footer>
    </main>
  );
}
