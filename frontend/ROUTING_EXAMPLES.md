# Routing & Number Extraction Examples

## Before Fix ❌

| User Says | System Did | Problem |
|-----------|-----------|---------|
| "find 5 leads" | Sent `limit: 10` | Ignored the "5" |
| "verify 3 companies" | Sent `limit: 5` | Ignored the "3" |
| "dispatch 7 loads" | Sent `load_count: 5` | Ignored the "7" |
| "5 verified leads" | Routed to hunt with `limit: 10` | Wrong number |

## After Fix ✅

| User Says | System Does | Result |
|-----------|------------|--------|
| "find 5 leads" | Sends `limit: 5` | ✅ Extracts 5 |
| "verify 3 companies" | Sends `limit: 3` | ✅ Extracts 3 |
| "dispatch 7 loads" | Sends `load_count: 7` | ✅ Extracts 7 |
| "hunt for 20 carriers" | Sends `limit: 20` | ✅ Extracts 20 |
| "investigate 8 leads" | Sends `limit: 8` | ✅ Extracts 8 |
| "match 15 shipments" | Sends `load_count: 15` | ✅ Extracts 15 |

## Routing Decision Tree

```
User Input
    ↓
Contains "find/hunt/search" + "lead/carrier/company"?
    ↓ YES
    HUNT ROUTE → Extract number → limit parameter

Contains "verify/investigate"?
    ↓ YES
    VERIFY ROUTE → Extract number → limit parameter

Contains "dispatch/match/load"?
    ↓ YES
    DISPATCH ROUTE → Extract number → load_count parameter

    ↓ NO MATCH
    DEFAULT: DISPATCH ROUTE (with defaults)
```

## Edge Cases Handled

### Multiple Numbers in Input
**Input:** "find 5 or maybe 10 leads"
**Result:** Extracts first number: `5`

### No Number Provided
**Input:** "find some leads"
**Result:** Uses default: `limit: 10`

### Complex Phrasing
**Input:** "can you please find me about 15 carrier companies?"
**Result:** Extracts `15`, routes to hunt

### Ambiguous Terms
**Input:** "I need leads for my loads"
**Priority:** HUNT route (checked first)
**Result:** Routes to hunt because "leads" + context

## API Request Bodies

### Hunt Request
```json
{
  "limit": 5,           // ← Extracted from user input
  "min_score": 0.6
}
```

### Verify Request
```json
{
  "limit": 3            // ← Extracted from user input
}
```

### Dispatch Request
```json
{
  "load_count": 7,      // ← Extracted from user input
  "matches_per_load": 3,
  "mock_mode": true
}
```

## Console Output Examples

### Example 1: "find 5 leads"
```
🚀 API Route: Received chat request
💬 Latest message: find 5 leads
🔢 Extracted number: 5 (default was 10)
🎯 Routing to HUNT (leads)
🔗 Calling Python backend: http://localhost:8000/v1/agent/hunt
📦 Request body: { limit: 5, min_score: 0.6 }
```

### Example 2: "verify 3 companies"
```
🚀 API Route: Received chat request
💬 Latest message: verify 3 companies
🔢 Extracted number: 3 (default was 5)
🎯 Routing to VERIFY
🔗 Calling Python backend: http://localhost:8000/v1/agent/verify
📦 Request body: { limit: 3 }
```

### Example 3: "dispatch 10 loads"
```
🚀 API Route: Received chat request
💬 Latest message: dispatch 10 loads
🔢 Extracted number: 10 (default was 5)
🎯 Routing to DISPATCH (loads)
🔗 Calling Python backend: http://localhost:8000/v1/agent/dispatch
📦 Request body: { load_count: 10, matches_per_load: 3, mock_mode: true }
```

## Testing Recommendations

### Test Set 1: Number Extraction
- [ ] "find 5 leads" → Should extract 5
- [ ] "hunt for 20 carriers" → Should extract 20
- [ ] "search 100 companies" → Should extract 100
- [ ] "find leads" → Should use default 10

### Test Set 2: Route Disambiguation
- [ ] "find leads" → Should route to HUNT
- [ ] "dispatch loads" → Should route to DISPATCH
- [ ] "verify leads" → Should route to VERIFY
- [ ] "5 verified leads" → Should route to HUNT (context)

### Test Set 3: Edge Cases
- [ ] "find 5 or 10 leads" → Should extract first: 5
- [ ] "I need leads" → Should route to HUNT with default
- [ ] "show me 15" → Should extract 15 (generic fallback)

## Pro Tips

1. **Check Console Logs**: Always monitor the console to see routing decisions
2. **Be Specific**: Use clear keywords like "find leads" or "dispatch loads"
3. **Include Numbers**: Always specify quantity for accurate results
4. **Use Correct Terms**:
   - Say "leads" when looking for carriers
   - Say "loads" when dispatching freight
