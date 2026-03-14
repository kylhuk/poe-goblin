

## OAuth Login via GGG (Path of Exile) — Backend-Handled Flow

### How it works

1. User clicks "Login" button in the header
2. Frontend opens a popup window pointing to the backend's OAuth initiation endpoint (e.g., `https://api.poe.lama-lan.ch/api/v1/auth/login`)
3. Backend redirects to GGG's OAuth page; user authorizes
4. Backend handles the callback, exchanges the code for a token, and redirects the popup to a frontend callback page with token/user info (via URL params or postMessage)
5. Frontend callback page sends the auth data back to the parent window via `window.opener.postMessage`
6. Parent window receives the message, stores the session, and updates the UI

### Unknowns to confirm

I need to check the backend's actual auth endpoints. I'll assume a common pattern:
- `GET /api/v1/auth/login?redirect_uri=...` — initiates OAuth, returns redirect to GGG
- The callback redirects to a URL we control with a token

**If the backend endpoints differ, we'll adjust during implementation.**

### Changes

**1. New file: `src/services/auth.ts`**
- Auth state management (user info, token) using a simple React context
- `login()` — opens popup to `${API_BASE}/api/v1/auth/login?redirect_uri=<callback_url>`
- `logout()` — clears stored token and user info
- Stores auth token in `localStorage`; injects it into API requests
- Listens for `postMessage` from the popup callback

**2. New file: `src/pages/AuthCallback.tsx`**
- Mounted at `/auth/callback` route
- Reads token/user info from URL search params
- Sends data to parent window via `postMessage`, then closes itself

**3. New file: `src/components/UserMenu.tsx`**
- Shows "Login" button when logged out
- Shows account name + avatar/icon + "Logout" button when logged in
- Placed in the header bar (right side, replacing or beside the disclaimer text)

**4. Modify `src/pages/Index.tsx`**
- Add `<UserMenu />` to the header

**5. Modify `src/App.tsx`**
- Wrap app in `<AuthProvider>`
- Add `/auth/callback` route

**6. Modify `src/services/api.ts`**
- In `request()`, also check for a user auth token (from auth context/localStorage) and include it in headers alongside or instead of the API key

### Auth state shape

```typescript
interface AuthUser {
  accountName: string;
  token: string;
}
```

Token and account name persisted in `localStorage` under a single key. On page load, hydrate from localStorage. On logout, clear it.

