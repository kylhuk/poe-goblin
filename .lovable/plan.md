

## Fix: Duplicate `handleSignOut` in UserMenu.tsx

### Problem
`handleSignOut` is declared twice — once at line 53 and again at line 61. This causes a TypeScript/ESBuild compilation error.

### Fix
Remove the first declaration (lines 53–56) and keep the second one (lines 61–65) which includes both `logout()` (PoE session) and `signOut()` (Supabase session). Move it above the `if (isLoading)` guard.

### Change in `src/components/UserMenu.tsx`
Replace lines 53–65:
```tsx
  const handleSignOut = async () => {
    logout();
    await signOut();
    setOpen(false);
  };

  if (isLoading) return null;

  const connected = sessionState === 'connected' && !!user;
```

This removes the duplicate and keeps the version that clears both auth layers.

