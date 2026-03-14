

## Problem

API errors are silently swallowed or shown as generic "Backend unavailable" text in small inline `RenderState` components. There's no centralized, visible way to see what's failing, what endpoint was called, or what error the backend returned. The `fetchSession` error in `auth.tsx` is completely unhandled (causes an unhandled promise rejection).

## Plan

### 1. Create an API error log store

Create `src/services/apiErrorLog.ts` — a simple in-memory ring buffer (last ~50 errors) using a Zustand store or plain reactive state. Each entry captures:
- Timestamp
- HTTP method + URL path
- Status code (or "network_error" for fetch failures)
- Error code + message from the response body
- Which component/caller triggered it (optional tag)

### 2. Hook the `request()` function into the error log

In `src/services/api.ts`, the existing `request()` catch path already parses error payloads. Add a call to push errors into the log store before re-throwing. Also catch network-level failures (`TypeError: Failed to fetch`) which currently aren't caught at all.

Similarly, wrap `fetchSession()` in `auth.tsx` to log fetch failures instead of letting them become unhandled rejections.

### 3. Add an API Status indicator in the header

In `src/pages/Index.tsx` header, add a small icon button (e.g. a `Terminal` or `Bug` icon) that:
- Shows a green/red dot based on whether recent errors exist
- On click, opens a slide-out Sheet or popover showing the error log entries in a scrollable list
- Each entry shows: time, endpoint, status, error message
- Include a "Clear" button

### 4. Fix the `SummaryCard` ref warning

The console error about `SummaryCard` not accepting refs — wrap it with `forwardRef` (same pattern as `RenderState`).

### Files to create/modify

| File | Change |
|---|---|
| `src/services/apiErrorLog.ts` | **New** — error log store (ring buffer + subscribe) |
| `src/services/api.ts` | Log errors in `request()` |
| `src/services/auth.tsx` | Catch + log `fetchSession` failures |
| `src/components/ApiErrorPanel.tsx` | **New** — Sheet/popover UI showing error log |
| `src/pages/Index.tsx` | Add error indicator button in header |
| `src/components/tabs/DashboardTab.tsx` | Wrap `SummaryCard` with `forwardRef` |

