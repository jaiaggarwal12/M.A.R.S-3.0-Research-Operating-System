"use client";

import { useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  type Edge,
  type Node,
  BackgroundVariant,
} from "reactflow";
import "reactflow/dist/style.css";
import { Network } from "lucide-react";
import { api } from "@/lib/api";

export default function GraphPage() {
  const [raw, setRaw] = useState<{ nodes: any[]; edges: any[] } | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.graphNetwork(80).then(setRaw).catch((e) => setErr(e.message));
  }, []);

  const { nodes, edges } = useMemo(() => {
    if (!raw?.nodes?.length) return { nodes: [] as Node[], edges: [] as Edge[] };
    const N = raw.nodes.length;
    const radius = Math.max(240, N * 14);
    const nodes: Node[] = raw.nodes.map((n, i) => {
      const angle = (i / N) * Math.PI * 2;
      const year = parseInt(n.year) || 2023;
      const hue = 250 - Math.min(30, (2026 - year) * 8);
      return {
        id: String(n.id),
        position: {
          x: Math.cos(angle) * radius + radius,
          y: Math.sin(angle) * radius + radius,
        },
        data: { label: (n.title || n.id).slice(0, 28) },
        style: {
          background: `hsl(${hue} 70% 20%)`,
          border: `1px solid hsl(${hue} 80% 55%)`,
          borderRadius: 10,
          color: "#e8e8f0",
          fontSize: 10,
          padding: 8,
          width: 150,
        },
      };
    });
    const ids = new Set(nodes.map((n) => n.id));
    const edges: Edge[] = (raw.edges || [])
      .filter((e) => ids.has(String(e.source)) && ids.has(String(e.target)))
      .map((e, i) => ({
        id: `e${i}`,
        source: String(e.source),
        target: String(e.target),
        style: { stroke: "rgba(124,92,255,0.25)" },
      }));
    return { nodes, edges };
  }, [raw]);

  return (
    <div className="flex h-screen flex-col px-8 py-8">
      <div className="mb-5 flex items-center gap-3">
        <Network className="h-6 w-6 text-accent-soft" />
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Knowledge Graph</h1>
          <p className="text-sm text-faint">
            Citation network · color encodes publication year.
          </p>
        </div>
      </div>

      <div className="card flex-1 overflow-hidden">
        {err && <p className="p-6 text-sm text-red-400">{err}</p>}
        {nodes.length ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            proOptions={{ hideAttribution: true }}
            className="bg-bg-soft"
          >
            <Background variant={BackgroundVariant.Dots} gap={24} color="#1e1e26" />
            <Controls className="!border-line !bg-bg-card" />
          </ReactFlow>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-faint">
            {err ? "" : "Run a research query first to build the graph."}
          </div>
        )}
      </div>
    </div>
  );
}
