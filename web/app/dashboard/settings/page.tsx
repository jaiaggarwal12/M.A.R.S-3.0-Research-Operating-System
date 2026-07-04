"use client";

import { useEffect, useState } from "react";
import { Settings, Cpu, Database, Server } from "lucide-react";
import { api, API_BASE } from "@/lib/api";

export default function SettingsPage() {
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: "down" }));
  }, []);

  const rows = [
    { icon: Server, label: "API Endpoint", value: API_BASE },
    { icon: Cpu, label: "LLM Provider", value: "Groq · Llama 3.3 70B" },
    { icon: Database, label: "Knowledge Graph", value: "Neo4j Aura" },
    {
      icon: Settings,
      label: "Backend Status",
      value: health?.status === "ok" ? "Online" : "Connecting…",
    },
  ];

  return (
    <div className="mx-auto max-w-3xl px-8 py-10">
      <div className="mb-8 flex items-center gap-3">
        <Settings className="h-6 w-6 text-accent-soft" />
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
      </div>

      <div className="card divide-y divide-line">
        {rows.map((r) => {
          const Icon = r.icon;
          return (
            <div key={r.label} className="flex items-center gap-4 px-6 py-4">
              <Icon className="h-4 w-4 text-accent-soft" />
              <div className="text-sm text-muted">{r.label}</div>
              <div className="ml-auto max-w-[60%] truncate text-sm font-medium text-white">
                {r.value}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
