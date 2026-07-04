import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "M.A.R.S 4.0 — Autonomous Research Operating System",
  description:
    "M.A.R.S 4.0 autonomously reads papers, builds knowledge graphs, designs experiments, generates hypotheses, evaluates them, and produces publication-ready research reports.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-bg text-white antialiased">
        {children}
      </body>
    </html>
  );
}
