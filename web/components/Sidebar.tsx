"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  FlaskConical,
  FileText,
  Network,
  Brain,
  Trophy,
  Boxes,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Command Center", icon: LayoutDashboard },
  { href: "/dashboard/research", label: "Research", icon: FlaskConical },
  { href: "/dashboard/reports", label: "Reports", icon: FileText },
  { href: "/dashboard/graph", label: "Knowledge Graph", icon: Network },
  { href: "/dashboard/memory", label: "Research Memory", icon: Brain },
  { href: "/dashboard/arena", label: "Arena", icon: Trophy },
  { href: "/dashboard/warehouse", label: "Warehouse", icon: Boxes },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-line bg-bg-soft px-3 py-5">
      <Link href="/" className="mb-8 flex items-center gap-2.5 px-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-gradient text-sm font-bold">
          M
        </div>
        <div>
          <div className="text-sm font-semibold leading-none tracking-tight">
            M.A.R.S
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-widest text-faint">
            Research OS
          </div>
        </div>
      </Link>

      <nav className="flex flex-1 flex-col gap-1">
        {NAV.map((item) => {
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "text-white"
                  : "text-faint hover:bg-bg-card hover:text-muted"
              )}
            >
              {active && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute inset-0 rounded-xl border border-accent/30 bg-accent/10"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <Icon className="relative h-4 w-4" />
              <span className="relative">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <Link
        href="/dashboard/settings"
        className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-faint transition-colors hover:bg-bg-card hover:text-muted"
      >
        <Settings className="h-4 w-4" /> Settings
      </Link>
    </aside>
  );
}
