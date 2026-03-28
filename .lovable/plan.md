

## Delete debug_traffic Table

Remove the `debug_traffic` table and all related frontend/backend code.

### Steps

1. **Database migration** — Drop the `debug_traffic` table
   ```sql
   DROP TABLE IF EXISTS public.debug_traffic;
   ```

2. **Delete edge function** — Remove `supabase/functions/debug-traffic-reader/index.ts`

3. **Delete frontend tab** — Remove `src/components/tabs/DebugTrafficTab.tsx`

4. **Update `src/pages/Index.tsx`** — Remove the "API Traffic" tab import and its tab panel entry

### Files affected
- `supabase/functions/debug-traffic-reader/index.ts` — delete
- `src/components/tabs/DebugTrafficTab.tsx` — delete
- `src/pages/Index.tsx` — remove debug traffic tab references

