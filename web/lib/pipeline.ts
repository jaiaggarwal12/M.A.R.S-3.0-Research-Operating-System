import {
  Search,
  Network,
  Brain,
  BookOpen,
  GitMerge,
  Lightbulb,
  Trophy,
  Users,
  FlaskConical,
  Play,
  BarChart3,
  Bot,
  FileText,
} from "lucide-react";

export interface Stage {
  id: string;
  label: string;
  desc: string;
  icon: any;
}

export const PIPELINE: Stage[] = [
  { id: "ingest", label: "Paper Retrieval", desc: "Arxiv + Semantic Scholar", icon: Search },
  { id: "graph", label: "Citation Graph", desc: "Neo4j + PageRank", icon: Network },
  { id: "memory", label: "Research Memory", desc: "Prior experiment recall", icon: Brain },
  { id: "literature", label: "Literature Review", desc: "Hybrid retrieval", icon: BookOpen },
  { id: "cross", label: "Cross-Paper Synthesis", desc: "Novel combinations", icon: GitMerge },
  { id: "hypothesis", label: "Hypothesis Generation", desc: "Falsifiable claims", icon: Lightbulb },
  { id: "arena", label: "Arena Scoring", desc: "Novelty · impact · feasibility", icon: Trophy },
  { id: "panel", label: "Specialist Panel", desc: "4-agent expert review", icon: Users },
  { id: "design", label: "Experiment Factory", desc: "6-file packages", icon: FlaskConical },
  { id: "run", label: "Execution", desc: "Metric capture", icon: Play },
  { id: "analyze", label: "Analysis", desc: "SOTA comparison", icon: BarChart3 },
  { id: "twin", label: "Digital Twin", desc: "Persona hypothesis", icon: Bot },
  { id: "report", label: "Research Report", desc: "Publication-ready", icon: FileText },
];
