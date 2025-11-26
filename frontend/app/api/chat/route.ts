import { streamText } from "ai";
import { createOpenAI } from "@ai-sdk/openai";

// Vercel route configuration - allow up to 60 seconds for long-running tasks
export const maxDuration = 60; // Maximum execution time in seconds
export const dynamic = "force-dynamic"; // Disable static optimization

// Python backend configuration
const PYTHON_BACKEND = process.env.PYTHON_BACKEND_URL || "http://localhost:8000";

// OpenAI configuration (for AI responses)
const openai = createOpenAI({
  apiKey: process.env.OPENAI_API_KEY || "",
});

export async function POST(req: Request) {
  try {
    console.log("🚀 API Route: Received chat request");
    const { messages } = await req.json();
    console.log("📝 Messages received:", messages.length);

    // Get the latest user message
    const latestMessage = messages[messages.length - 1];
    const userInput = latestMessage.content.toLowerCase();
    console.log("💬 Latest message:", latestMessage.content);

    // Extract numbers from user input
    const extractNumber = (text: string, defaultValue: number): number => {
      // Look for patterns like "5 leads", "get 10 carriers", "find 20 companies"
      const numberMatch = text.match(/\b(\d+)\b/);
      if (numberMatch) {
        const num = parseInt(numberMatch[1], 10);
        console.log(`🔢 Extracted number: ${num} (default was ${defaultValue})`);
        return num;
      }
      console.log(`🔢 No number found, using default: ${defaultValue}`);
      return defaultValue;
    };

    // Determine which Python endpoint to call based on user intent
    let endpoint = "/v1/agent/dispatch";
    let requestBody: any = {
      message: latestMessage.content,
    };

    // Route to appropriate Python backend endpoint
    // Priority order: hunt (leads) > verify > dispatch (loads)
    if (
      (userInput.includes("find") || userInput.includes("hunt") || userInput.includes("search")) &&
      (userInput.includes("lead") || userInput.includes("carrier") || userInput.includes("company"))
    ) {
      // Hunt for leads
      endpoint = "/v1/agent/hunt";
      const limit = extractNumber(userInput, 10);
      requestBody = {
        limit: limit,
        min_score: 0.6,
      };
      console.log("🎯 Routing to HUNT (leads)");
    } else if (userInput.includes("verify") || userInput.includes("investigate")) {
      // Verify leads
      endpoint = "/v1/agent/verify";
      const limit = extractNumber(userInput, 5);
      requestBody = {
        limit: limit,
      };
      console.log("🎯 Routing to VERIFY");
    } else if (
      userInput.includes("dispatch") ||
      userInput.includes("match") ||
      userInput.includes("load")
    ) {
      // Dispatch loads
      endpoint = "/v1/agent/dispatch";
      const loadCount = extractNumber(userInput, 5);
      requestBody = {
        load_count: loadCount,
        matches_per_load: 3,
        mock_mode: true,
      };
      console.log("🎯 Routing to DISPATCH (loads)");
    }

    // Try to call Python backend (if available)
    let backendResponse = null;
    try {
      const backendUrl = `${PYTHON_BACKEND}${endpoint}`;
      console.log("🔗 Calling Python backend:", backendUrl);
      console.log("📦 Request body:", requestBody);

      // Create AbortController with 60-second timeout for long-running backend operations
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        console.warn("⏱️ Backend request timeout (60s), aborting...");
        controller.abort();
      }, 60000); // 60 seconds

      const response = await fetch(backendUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
        signal: controller.signal,
      });

      clearTimeout(timeoutId); // Clear timeout if request completes
      console.log("📡 Backend response status:", response.status, response.statusText);

      if (response.ok) {
        backendResponse = await response.json();
        console.log("✅ Backend response received:", backendResponse);
      } else {
        console.warn("⚠️ Backend returned non-OK status:", response.status);
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        console.error("⏱️ Python backend request timed out after 60 seconds");
      } else {
        console.error("❌ Python backend error:", error);
      }
      console.error("Backend URL was:", `${PYTHON_BACKEND}${endpoint}`);
      // Continue with AI-only response if backend is unavailable or timed out
    }

    // Generate AI response using Vercel AI SDK
    const systemPrompt = `You are the Al-Buraq Dispatcher AI Assistant, an ethical freight dispatch system.

IMPORTANT TERMINOLOGY:
- "LEADS" = Potential carrier companies to work with (hunt/find/search for new carriers)
- "LOADS" = Freight shipments to be dispatched (match loads to carriers)

Your capabilities:
1. HUNT FOR LEADS: Find new carrier companies
   - User says: "find 5 leads", "hunt for 10 carriers", "search for companies"
   - System extracts the number and uses it as the limit

2. VERIFY LEADS: Investigate carrier companies for social media presence
   - User says: "verify 3 leads", "investigate 8 companies"
   - System extracts the number and uses it as the limit

3. DISPATCH LOADS: Match freight shipments to verified carriers
   - User says: "dispatch 5 loads", "match 10 shipments"
   - System extracts the number and uses it as load count

IMPORTANT RULES (from MISSION.md):
1. Only accept HALAL freight (no alcohol, tobacco, pork, weapons, etc.)
2. Commission is ALWAYS 7% of the load rate
3. Charity contribution is ALWAYS 5% of the load rate
4. Be honest and transparent in all dealings

${backendResponse ? `\n\nLatest Backend Data:\n${JSON.stringify(backendResponse, null, 2)}` : ""}

When responding:
- If backend data is available, summarize the results clearly
- Always confirm the NUMBER the user requested (e.g., "I found 5 verified leads as requested")
- Distinguish between LEADS (carriers) and LOADS (freight)
- If the backend is unavailable, explain what you would do and suggest they ensure the Python server is running`;

    console.log("🤖 Calling OpenAI with model: gpt-4o");
    console.log("📋 System prompt length:", systemPrompt.length);

    const result = streamText({
      model: openai("gpt-4o"),
      system: systemPrompt,
      messages,
    });

    console.log("✅ Streaming text response initiated");
    return result.toTextStreamResponse();
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
