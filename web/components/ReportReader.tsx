"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion } from "framer-motion";
import { Download, FileText } from "lucide-react";
import type { ResearchResult } from "@/lib/api";

export function ReportReader({ result }: { result: ResearchResult }) {
  const download = () => {
    const blob = new Blob([result.final_report], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mars-report-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="card overflow-hidden"
    >
      <div className="flex items-center justify-between border-b border-line px-6 py-4">
        <div className="flex items-center gap-2.5">
          <FileText className="h-4 w-4 text-accent-soft" />
          <span className="text-sm font-semibold">Research Report</span>
        </div>
        <button onClick={download} className="btn-ghost py-2 text-xs">
          <Download className="h-3.5 w-3.5" /> Markdown
        </button>
      </div>

      {/* metric strip */}
      <div className="grid grid-cols-3 gap-px border-b border-line bg-line md:grid-cols-6">
        {[
          ["Papers", result.papers_indexed],
          ["Graph", result.graph_nodes],
          ["Hypotheses", result.hypotheses_count],
          ["Experiments", result.experiments_run],
          ["Discoveries", result.successful_discoveries],
          ["Latency", `${result.latency_sec}s`],
        ].map(([label, val]) => (
          <div key={String(label)} className="bg-bg-card px-3 py-3 text-center">
            <div className="text-lg font-bold">{val}</div>
            <div className="text-[10px] uppercase tracking-wider text-faint">
              {label}
            </div>
          </div>
        ))}
      </div>

      <div className="prose-report max-h-[70vh] overflow-y-auto px-8 py-7">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {result.final_report || "_No report generated._"}
        </ReactMarkdown>
      </div>

      <style jsx global>{`
        .prose-report h1 {
          font-size: 1.6rem;
          font-weight: 800;
          margin: 1.2rem 0 0.6rem;
          letter-spacing: -0.02em;
        }
        .prose-report h2 {
          font-size: 1.2rem;
          font-weight: 700;
          margin: 1.4rem 0 0.5rem;
          color: #d8d8e2;
        }
        .prose-report h3 {
          font-size: 1rem;
          font-weight: 600;
          margin: 1rem 0 0.4rem;
          color: #c4c4d0;
        }
        .prose-report p,
        .prose-report li {
          color: #a8a8b6;
          line-height: 1.7;
          font-size: 0.92rem;
          margin: 0.4rem 0;
        }
        .prose-report strong {
          color: #ededf2;
        }
        .prose-report table {
          width: 100%;
          border-collapse: collapse;
          margin: 1rem 0;
          font-size: 0.85rem;
        }
        .prose-report th,
        .prose-report td {
          border: 1px solid #1e1e26;
          padding: 0.5rem 0.75rem;
          text-align: left;
        }
        .prose-report th {
          background: #16161c;
          color: #d8d8e2;
          font-weight: 600;
        }
        .prose-report code {
          background: #16161c;
          padding: 0.1rem 0.4rem;
          border-radius: 6px;
          font-size: 0.82rem;
          color: #9d84ff;
        }
        .prose-report a {
          color: #9d84ff;
        }
        .prose-report ul {
          padding-left: 1.2rem;
          list-style: disc;
        }
      `}</style>
    </motion.div>
  );
}
