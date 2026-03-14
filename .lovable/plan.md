

## Plan: Replace "Login via PoE" with a Settings Dropdown for POESESSID

### What Changes

Replace the login button in `UserMenu` with a **Settings** dropdown (using a `Popover`) where the user can input their `POESESSID` string. The value gets stored as a cookie so the backend can read it via `credentials: 'include'`.

### Files to Modify

**1. `src/components/UserMenu.tsx`** — Full rewrite
- Remove the `login` button and OAuth popup flow
- Add a Settings icon button (gear icon) that opens a `Popover`
- Inside the popover: an input field for POESESSID, a Save button, and a Clear button
- On Save: write `document.cookie = "POESESSID=<value>; path=/; SameSite=Lax; max-age=31536000"` and call `refreshSession()` to re-check auth state
- On Clear: delete the cookie (`max-age=0`), call `refreshSession()`
- Show current status: if connected, display the account name; if not, show "Not connected"
- Read current POESESSID from cookies on mount to pre-fill the input (masked)

**2. `src/services/auth.tsx`** — Minor update
- Remove the `login` callback (popup OAuth flow) from the context since it's no longer used
- Keep `refreshSession` and `logout` — logout should also clear the POESESSID cookie
- Update `AuthContextValue` interface accordingly (remove `login`)

### Cookie Details
- Name: `POESESSID`
- Path: `/` (so the backend receives it on all requests via `credentials: 'include'`)
- `SameSite=Lax`, no `Secure` flag (to work in dev)
- Max-age: 1 year on save, 0 on clear

### UI Layout
The popover will contain:
- Label: "POESESSID"
- Text input (type `password` to mask, with a show/hide toggle)
- Save / Clear buttons
- Status line showing connection state

