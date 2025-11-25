import { streamText } from "ai";
import { createOpenAI } from "@ai-sdk/openai";

// Python backend configuration
const PYTHON_BACKEND = process.env.PYTHON_BACKEND_URL || "http://localhost:8000";

// OpenAI configuration (for AI responses)
const openai = createOpenAI({
  apiKey: process.env.OPENAI_API_KEY || "",
});

export async function POST(req: Request) {
  try {
    const { messages } = await req.json();

    // Get the latest user message
    const latestMessage = messages[messages.length - 1];
    const userInput = latestMessage.content.toLowerCase();

    // Determine which Python endpoint to call based on user intent
    let endpoint = "/v1/agent/dispatch";
    let requestBody: any = {
      message: latestMessage.content,
    };

    // Route to appropriate Python backend endpoint
    if (userInput.includes("find") || userInput.includes("hunt") || userInput.includes("lead")) {
      endpoint = "/v1/agent/hunt";
      requestBody = {
        limit: 10,
        min_score: 0.6,
      };
    } else if (userInput.includes("verify") || userInput.includes("investigate")) {
      endpoint = "/v1/agent/verify";
      requestBody = {
        limit: 5,
      };
    } else if (userInput.includes("dispatch") || userInput.includes("match")) {
      endpoint = "/v1/agent/dispatch";
      requestBody = {
        loads: 5,
        matches: 3,
      };
    }

    // Try to call Python backend (if available)
    let backendResponse = null;
    try {
      const response = await fetch(`${PYTHON_BACKEND}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (response.ok) {
        backendResponse = await response.json();
      }
    } catch (error) {
      console.error("Python backend error:", error);
      // Continue with AI-only response if backend is unavailable
    }

    // Generate AI response using Vercel AI SDK
    const systemPrompt = `You are the Al-Buraq Dispatcher AI Assistant, an ethical freight dispatch system.

Your capabilities:
- Hunt for carrier leads (use "find leads" or "hunt")
- Verify leads through investigation (use "verify" or "investigate")
- Dispatch loads to carriers (use "dispatch" or "match")

IMPORTANT RULES (from MISSION.md):
1. Only accept HALAL freight (no alcohol, tobacco, pork, weapons, etc.)
2. Commission is ALWAYS 7% of the load rate
3. Charity contribution is ALWAYS 5% of the load rate
4. Be honest and transparent in all dealings

${backendResponse ? `\n\nLatest Backend Data:\n${JSON.stringify(backendResponse, null, 2)}` : ""}

Respond helpfully to the user's request. If backend data is available, use it in your response.
If the backend is unavailable, explain what you would do and suggest they ensure the Python server is running.`;

    const result = streamText({
      model: openai("gpt-4o"),
      system: systemPrompt,
      messages,
    });

    return result.toDataStreamResponse();
  } catch (error) {
    console.error("Chat API error:", error);
    return new Response(
      JSON.stringify({
        error: "Failed to process request",
        details: error instanceof Error ? error.message : String(error)
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" }
      }
    );
  }
}
