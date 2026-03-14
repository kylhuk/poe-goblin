# Draft: Public PKCE Account Stash

## Requirements (confirmed)
- private stash access without a confidential OAuth client
- do not use `POESESSID` or undocumented session-cookie auth
- use a public OAuth client with PKCE and loopback callback
- target account data needed for stash access (`account:stashes`, likely `account:profile`)

## Technical Decisions
- keep the existing `/api/v1/auth/login` and `/api/v1/auth/callback` flow as the integration surface
- replace the current simulated callback/session flow with a real authorization-code exchange
- use a loopback redirect URI suitable for a PoE public client
- keep tokens server-side/local-service-side; frontend continues to rely on session cookie state
- first cut will power live stash reads through the authenticated API session instead of wiring the background `account_stash_harvester`
- reuse `poe_trade.ingestion.poe_client.PoeClient` and the existing service-scope OAuth request shape as the pattern for token exchange/refresh

## Research Findings
- `poe_trade/api/auth_session.py` already generates PKCE verifier/challenge and authorize URL
- `poe_trade/api/app.py` currently starts login but does not exchange the authorization code at `/oauth/token`
- `frontend/src/pages/AuthCallback.tsx` already closes the popup and notifies the opener after backend redirect completion
- `poe_trade/services/account_stash_harvester.py` currently depends on a static `POE_ACCOUNT_STASH_ACCESS_TOKEN`
- official PoE docs support public clients with PKCE + loopback redirect for account scopes including `account:stashes`

## Open Questions
- whether refresh-token persistence should survive process restarts or remain ephemeral for the first cut

## Scope Boundaries
- INCLUDE: public-client PKCE login, token exchange, session state, live stash access enablement through API routes
- EXCLUDE: undocumented `POESESSID` auth, confidential-client flow, unrelated service-scope changes
- EXCLUDE: background `account_stash_harvester` token wiring in the first cut
