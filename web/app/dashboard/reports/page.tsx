"use client";

import Link from "next/link";
import { FileText, ArrowRight } from "lucide-react";

export default function ReportsPage() {
  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <div className="mb-8 flex items-center gap-3">
        <FileText className="h-6 w-6 text-accent-soft" />
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Reports</h1>
          <p className="text-sm text-faint">
            Publication-ready research reports from completed cycles.
          </p>
        </div>
      </div>

      <div className="card flex flex-col items-center justify-center p-16 text-center">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-line bg-bg-elevated">
          <FileText className="h-6 w-6 text-accent-soft" />
        </div>
        <h3 className="text-lg font-semibold">No reports in this session yet</h3>
        <p className="mt-2 max-w-sm text-sm text-muted">
          Run a research cycle to generate a full report. Reports are rendered
          live and can be exported as Markdown.
        </p>
        <Link href="/dashboard/research" className="btn-primary mt-6">
          Start research <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
