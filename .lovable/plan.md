

## Fix Stash Tab Switching Being Overwritten by Polling

### Problem

When clicking a different tab, `loadTab` correctly fetches and displays that tab's items. However, `loadPublished` runs every 5 seconds and also calls `api.getStashTabs(activeTabIndex)`, overwriting `activeTab` with stale data. This causes the grid to snap back or show wrong items.

### Root Cause

`loadPublished` does two things it shouldn't:
1. It re-fetches the active tab's items on every poll — unnecessary since the tab data only changes on scan publish
2. The 5-second polling interval means any tab switch gets overwritten almost immediately

### Fix — `src/components/tabs/StashViewerTab.tsx`

**Separate status polling from tab data loading:**

- `loadPublished` should only call `api.getStashStatus()` for scan status, published scan ID, and connection state. It should NOT call `api.getStashTabs()` or touch `activeTab`.
- Remove `activeTabIndex` from `loadPublished`'s dependency array.
- Initial tab load: call `loadTab(0)` once on mount (after status confirms connected).
- Tab clicks: call `loadTab(tabIndex)` as they already do — this is the only place that fetches tab items.
- When a scan finishes (`published` status detected), call `loadTab(activeTabIndex)` to refresh the current tab's items with the new snapshot.

### Files Changed

- `src/components/tabs/StashViewerTab.tsx` — decouple status polling from tab data fetching

