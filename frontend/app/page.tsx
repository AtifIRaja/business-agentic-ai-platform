"use client";

import { useEffect, useRef, useState } from "react";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const url = "/api/chat";
      console.log("Sending request to:", url);
      console.log("Backend API URL:", apiUrl);
      console.log("Request payload:", { messages: [...messages, userMessage] });

      // Create AbortController with 65-second timeout (slightly longer than backend)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        console.warn("⏱️ Frontend request timeout (65s), aborting...");
        controller.abort();
      }, 65000); // 65 seconds

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: [...messages, userMessage],
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId); // Clear timeout if request starts
      console.log("Response status:", response.status, response.statusText);

      if (!response.ok) {
        throw new Error("Failed to get response");
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = "";

      const assistantId = (Date.now() + 1).toString();

      console.log("Starting to read response stream...");

      if (reader) {
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              console.log("✅ Stream complete. Total message length:", assistantMessage.length);
              break;
            }

            const chunk = decoder.decode(value, { stream: true });
            assistantMessage += chunk;
            console.log("📨 Received chunk:", chunk.substring(0, 50) + "...");

            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage && lastMessage.id === assistantId) {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMessage, content: assistantMessage },
                ];
              } else {
                return [
                  ...prev,
                  { id: assistantId, role: "assistant", content: assistantMessage },
                ];
              }
            });
          }
        } catch (streamError) {
          console.error("❌ Stream reading error:", streamError);
          // If we got partial content, keep it
          if (assistantMessage.length > 0) {
            console.log("Keeping partial message:", assistantMessage.length, "characters");
          } else {
            throw streamError;
          }
        } finally {
          reader.releaseLock();
        }
      } else {
        throw new Error("No response body available");
      }
    } catch (error) {
      console.error("❌ Error occurred:", error);
      console.error("Error details:", {
        message: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      });

      let errorMessage = "Sorry, I encountered an error. Please try again.";

      if (error instanceof Error) {
        if (error.name === "AbortError") {
          errorMessage = "⏱️ Request timed out after 65 seconds. The backend might be processing a large request. Please try again or check if the Python backend is running.";
        } else if (error.message.includes("fetch")) {
          errorMessage = "🔌 Cannot connect to the API. Please ensure the server is running.";
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "assistant",
          content: errorMessage,
        },
      ]);
    } finally {
      console.log("Request completed. isLoading set to false.");
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full flex-col bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm px-6 py-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/80">
        <div className="flex items-center justify-between max-w-5xl mx-auto">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              Al-Buraq Dispatcher
            </h1>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Ethical AI Dispatch System - CAARE Q3 Week 12
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-xs text-slate-600 dark:text-slate-400">
              Backend: {apiUrl}
            </span>
          </div>
        </div>
      </header>

      {/* Chat Interface */}
      <main className="flex-1 overflow-hidden flex flex-col max-w-5xl w-full mx-auto">
        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="bg-white dark:bg-slate-800 rounded-2xl p-8 shadow-lg border border-slate-200 dark:border-slate-700 max-w-md">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-2">
                  Welcome to Al-Buraq
                </h2>
                <p className="text-slate-600 dark:text-slate-400 mb-4">
                  Your ethical AI dispatch system. Ask me anything, and I'll route your request to the best agent.
                </p>
                <div className="grid grid-cols-1 gap-2 text-sm text-left">
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
                    <p className="text-slate-700 dark:text-slate-300">💡 Try: "Create a marketing strategy"</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
                    <p className="text-slate-700 dark:text-slate-300">💡 Try: "Analyze this business plan"</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
                    <p className="text-slate-700 dark:text-slate-300">💡 Try: "Help with technical documentation"</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 shadow-sm ${
                      message.role === "user"
                        ? "bg-blue-600 text-white"
                        : "bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 border border-slate-200 dark:border-slate-700"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {message.role === "assistant" && (
                        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-white text-xs font-bold">
                          AI
                        </div>
                      )}
                      <div className="flex-1 whitespace-pre-wrap break-words">
                        {message.content}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-white text-xs font-bold">
                        AI
                      </div>
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-2">
                          <div className="flex gap-1">
                            <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                            <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                            <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                          </div>
                          <span className="text-sm text-slate-600 dark:text-slate-400">Processing your request...</span>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-500">
                          This may take up to 60 seconds for complex queries involving the backend system.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input Form */}
        <div className="border-t border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm p-4">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message here..."
              disabled={isLoading}
              className="flex-1 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-4 py-3 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="rounded-xl bg-blue-600 px-6 py-3 font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? "Sending..." : "Send"}
            </button>
          </form>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm px-6 py-3">
        <p className="text-center text-xs text-slate-600 dark:text-slate-400 max-w-5xl mx-auto">
          Built with integrity, dispatched with honesty - Next.js & Vercel AI SDK
        </p>
      </footer>
    </div>
  );
}
