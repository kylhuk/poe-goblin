
## Task 2: Data Volume Verification for v_ps_items_enriched View

**Findings from Tue Mar 17 09:32:37 CET 2026:**
- 7-day window count for Mirage league: 16,041,977 rows
- Total count for Mirage league: 16,041,977 rows
- The 7-day time boundary does NOT reduce scan volume significantly for Mirage league
- All data in the view for Mirage league appears to be within the last 7 days

**Conclusion:** The 7-day boundary in the view definition may not be providing the expected performance benefit for the Mirage league, as all current data falls within this window.



## API Response Format Verification (2026-03-17)

Verified the PoeNinja API response format for currency overview endpoint:
- URL: https://poe.ninja/poe1/api/economy/stash/current/currency/overview?league=Mirage&type=Currency
- Response contains `lines` array with 89 entries and `currencyDetails` array with 284 entries
- Each line entry contains:
  - ✓ chaosEquivalent (float): 0.0039999999999999997
  - ✓ currencyTypeName (string): "Orb of Alteration"  
  - ✓ detailsId (string): "2575"
  - ✗ count (not directly in line entries)
    - Found nested in pay.count and receive.count fields
    - Example: pay.count: 5, receive.count: 36

Conclusion: The API provides chaosEquivalent, currencyTypeName, and detailsId directly in lines[] entries as required.
The count field is available as pay.count and receive.count within each entry.
