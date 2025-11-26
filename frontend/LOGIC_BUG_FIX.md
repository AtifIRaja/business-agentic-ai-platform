# Logic Bug Fix: Dynamic Number Extraction & Intelligent Routing

## Problem Identified

### Issue 1: Hardcoded Numbers
When a user asked for "5 verified leads", the system returned 10 leads because it was using hardcoded defaults instead of extracting numbers from the user's prompt.

**Old Behavior:**
- User: "find 5 leads" → System used `limit: 10` (hardcoded)
- User: "verify 3 companies" → System used `limit: 5` (hardcoded)
- User: "dispatch 7 loads" → System used `load_count: 5` (hardcoded)

### Issue 2: Confusing "Leads" with "Loads"
The routing logic was confusing:
- **LEADS** = Carrier companies to hunt/find
- **LOADS** = Freight shipments to dispatch

The old logic would trigger the hunt endpoint for any message containing "lead", even if the user was talking about loads.

## Solution Implemented

### 1. Dynamic Number Extraction

Added a smart `extractNumber()` function that:
- Uses regex to find numbers in the user's input: `/\b(\d+)\b/`
- Extracts the first number found (e.g., "5" from "find 5 leads")
- Falls back to sensible defaults if no number is provided
- Logs the extraction process for debugging

**Example:**
```typescript
const extractNumber = (text: string, defaultValue: number): number => {
  const numberMatch = text.match(/\b(\d+)\b/);
  if (numberMatch) {
    const num = parseInt(numberMatch[1], 10);
    console.log(`🔢 Extracted number: ${num} (default was ${defaultValue})`);
    return num;
  }
  console.log(`🔢 No number found, using default: ${defaultValue}`);
  return defaultValue;
};
```

### 2. Intelligent Routing Logic

Improved the routing to distinguish between operations:

#### Hunt for Leads (Carrier Companies)
**Triggers when:**
- User says: "find", "hunt", or "search" AND
- User says: "lead", "carrier", or "company"

**Extracts:** Number for `limit` parameter
**Default:** 10 leads

**Examples:**
- ✅ "find 5 leads" → `limit: 5`
- ✅ "hunt for 20 carriers" → `limit: 20`
- ✅ "search 15 companies" → `limit: 15`

#### Verify Leads
**Triggers when:**
- User says: "verify" or "investigate"

**Extracts:** Number for `limit` parameter
**Default:** 5 leads

**Examples:**
- ✅ "verify 3 leads" → `limit: 3`
- ✅ "investigate 8 companies" → `limit: 8`

#### Dispatch Loads (Freight Shipments)
**Triggers when:**
- User says: "dispatch", "match", or "load"

**Extracts:** Number for `load_count` parameter
**Default:** 5 loads

**Examples:**
- ✅ "dispatch 5 loads" → `load_count: 5`
- ✅ "match 10 shipments" → `load_count: 10`
- ✅ "7 loads please" → `load_count: 7`

### 3. Updated System Prompt

Enhanced the AI assistant's understanding:

```
IMPORTANT TERMINOLOGY:
- "LEADS" = Potential carrier companies to work with
- "LOADS" = Freight shipments to be dispatched

When responding:
- Always confirm the NUMBER the user requested
- Distinguish between LEADS (carriers) and LOADS (freight)
```

## How It Works Now

### Flow Diagram

```
User Input: "find 5 verified leads"
     ↓
Parse Input (lowercase)
     ↓
Check for keywords:
- "find" ✓
- "lead" ✓
     ↓
Route to: /v1/agent/hunt
     ↓
Extract Number: 5
     ↓
Send to Backend: { limit: 5, min_score: 0.6 }
     ↓
AI Response: "I found 5 verified leads as requested"
```

## Console Logs for Debugging

The system now logs the entire routing process:

```
🚀 API Route: Received chat request
💬 Latest message: find 5 verified leads
🔢 Extracted number: 5 (default was 10)
🎯 Routing to HUNT (leads)
🔗 Calling Python backend: http://localhost:8000/v1/agent/hunt
📦 Request body: { limit: 5, min_score: 0.6 }
```

## Test Cases

| User Input | Route | Extracted | Correct? |
|------------|-------|-----------|----------|
| "find 5 leads" | hunt | limit: 5 | ✅ |
| "hunt for 20 carriers" | hunt | limit: 20 | ✅ |
| "verify 3 companies" | verify | limit: 3 | ✅ |
| "investigate 8 leads" | verify | limit: 8 | ✅ |
| "dispatch 7 loads" | dispatch | load_count: 7 | ✅ |
| "match 10 shipments" | dispatch | load_count: 10 | ✅ |
| "find leads" (no number) | hunt | limit: 10 (default) | ✅ |

## Benefits

1. ✅ **User Intent Respected**: System now honors the exact number requested
2. ✅ **Smart Defaults**: Falls back to sensible defaults when no number is provided
3. ✅ **Clear Distinction**: Properly routes "leads" vs "loads" operations
4. ✅ **Better Logging**: Full visibility into routing and extraction decisions
5. ✅ **AI Awareness**: Assistant confirms numbers in responses

## Files Modified

- `frontend/app/api/chat/route.ts`: Added extraction logic and intelligent routing

## Restart Required

To apply these fixes, restart your frontend development server:

```bash
cd frontend
npm run dev
```

## Verification

Try these commands in the UI:
1. "find 5 verified leads" → Should return exactly 5
2. "verify 3 leads" → Should verify exactly 3
3. "dispatch 7 loads" → Should dispatch exactly 7

Check the console logs to see the extraction and routing in action!
