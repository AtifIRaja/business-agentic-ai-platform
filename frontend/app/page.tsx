"use client";

import { Thread } from "@assistant-ui/react";
import { useEdgeRuntime } from "@assistant-ui/react-ai-sdk";

export default function Home() {
  const runtime = useEdgeRuntime({
    api: "/api/chat",
  });

  return (
    <div className="flex h-screen w-full flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">
              Al-Buraq Dispatcher
            </h1>
            <p className="text-sm text-muted-foreground">
              Ethical AI Dispatch System - CAARE Q3 Week 12
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-green-500" />
            <span className="text-xs text-muted-foreground">
              Connected to localhost:8000
            </span>
          </div>
        </div>
      </header>

      {/* Chat Interface */}
      <main className="flex-1 overflow-hidden">
        <Thread runtime={runtime} />
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-card px-6 py-3">
        <p className="text-center text-xs text-muted-foreground">
          Built with integrity, dispatched with honesty - OpenAI Assistant UI + Vercel AI SDK
        </p>
      </footer>
    </div>
  );
}
