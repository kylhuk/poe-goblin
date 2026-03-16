

## Add User Approval Gate

### Problem
After registering, users can immediately access the app. You need manual control over who gets access.

### Approach
Create an `approved_users` table. After login, the app checks if the user's ID exists in that table. If not, they see a "pending approval" screen instead of the app. You manually add users to the table to grant access.

### Database
- New `approved_users` table with `user_id` (uuid, references auth.users, unique) and `approved_at` timestamp
- RLS policy: authenticated users can read their own row only

```sql
CREATE TABLE public.approved_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
  approved_at timestamptz DEFAULT now()
);

ALTER TABLE public.approved_users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can check own approval"
  ON public.approved_users FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());
```

### Code Changes

**`src/services/auth.tsx`**
- After Supabase session is established, query `approved_users` for the current user's ID
- Add `isApproved` boolean to context (default `false`)
- `isAuthenticated` stays true (they *are* logged in), but add `isApproved` as a separate flag

**`src/App.tsx`**
- Gate changes: if authenticated but NOT approved, show a "Pending Approval" message with a sign-out button instead of the app
- If not authenticated at all, show Login

**`src/pages/Login.tsx`**
- After successful sign-up, show message: "Account created — waiting for approval"

### Granting Access
You add users via the backend data UI: insert a row into `approved_users` with the user's ID. The user refreshes and gets in.

### Files
1. Database migration — `approved_users` table + RLS
2. `src/services/auth.tsx` — add `isApproved` check
3. `src/App.tsx` — gate on `isApproved`
4. `src/pages/Login.tsx` — post-signup messaging

