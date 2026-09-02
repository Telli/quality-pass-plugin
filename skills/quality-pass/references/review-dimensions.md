# Review dimensions — what each reviewer hunts for

Every finding needs `file:line` (or a measured number from a build/profile). "Looks suspicious" is not a finding. Each reviewer reports in the contract at the bottom of this file.

## 1. Slop & honesty

- Fabricated stats, SLAs, customer counts, testimonials, "trusted by" logos, uptime claims not derived from data
- Placeholder copy ("Lorem", "Refer to the PRD", "Coming soon" with no ticket), scaffold names left in package/app metadata
- Brand name split or spelled two ways; two accent color systems; two icon libraries; emoji used as icons; literal ✕ → • glyphs in place of icons
- Gradient / glassmorphism clichés on primary CTAs; hardcoded blue→purple
- Fake UI state: static "All systems operational", hardcoded badges/dots/counters, success toasts for saves that never call an API, forms bound to constants
- `href="#"` legal/footer links, 404 routes linked from the UI
- Dark/light theme pairs missing tokens (success/warning/info/shadow), ad-hoc palettes in individual pages
- README / marketing claims contradicted by the code (e.g. "every action requires approval" vs an autonomy mode)

## 2. Bugs

- **Logout/teardown**: query cache not cleared, sockets/subscriptions surviving logout, user-scoped localStorage keys never cleared, cache keys without user/tenant → cross-user data on a shared machine
- **Reconnect state machines**: fixed retry arrays that give up forever, no `onclose` restart, no invalidation on reconnect, poll fallback that never engages
- **Token refresh**: no single-flight, no timeout on the refresh call (a black-holed refresh pins `isRefreshing` forever), queued replays not marked as retried
- **Missing timeouts** on HTTP clients and out-of-band requests
- **Sync cursors** derived from sender-controlled fields (one future-dated item freezes sync forever)
- **Idempotency**: retries that create duplicates because the dedupe key differs from the write key; jobs that save once at the end and lose progress on crash; no reaper for stale "in progress" rows
- **Copy-into-state antipatterns**: props/API data copied into local state with `length > 0` guards (deleting the last item never clears), background refetches clobbering unsaved edits
- Off-by-one on calendar dates and timezones; wrong recipient key (Employee PK vs User PK); enum/string mismatches between backend and frontend

## 3. Security & data integrity

- Endpoints without authorization or with the wrong policy; resource-membership checks expressed as flat permissions
- Tenant/owner scoping missing on a query the endpoint reaches (digests, exports, search, "list all" admin paths); global query filters that fail open when the tenant claim is absent
- Enumeration: search endpoints that return identifiers on short prefixes; sequential IDs exposed
- Secrets stored plaintext or echoed back in list/detail APIs; tokens in logs; webhook signatures not verified
- Unbounded `pageSize`, missing max clamps, unpaginated "get all" used by pushes
- Private data egress to third parties (AI providers, analytics) without the classification check the product claims
- Cascade deletes that erase history the product promises to keep (assignment/audit trails)
- World-readable templates/files, public buckets, missing `Cache-Control` on private responses

## 4. Performance

Build the production bundle and read the output (sizes, sourcemaps, chunk graph). Never guess.

- Chunk catch-alls swallowing lazily-loaded deps into the entry; heavy libs (xlsx, pdf, charts, editors, realtime clients) in the entry or a shared chunk
- Barrel imports dragging whole libraries in; multi-MB images served at icon sizes
- Store/context subscriptions without selectors; provider values recreated every render; timers that re-render the whole app
- Unmemoized lists under high-frequency updates (chat, logs, live feeds); input state that re-renders a sibling list per keystroke
- Per-message writes that should batch; polling that ignores an existing live push; push handlers that invalidate an unpaginated query
- Backend: N+1 queries, cartesian blow-ups from multi-collection includes, missing `AsNoTracking`/split query on read paths, O(n²) tree builds, missing response compression and immutable asset caching

## 5. Dead code

Report candidates only; the executor applies the two-pattern rule before any deletion.

- Zero-importer files, exports, and components; duplicate components with diverging APIs
- `*.old.*`, `*Live*`/`Standard*` supersession leftovers, `.bak`, orphan builds/artifacts committed or untracked
- npm/NuGet/pip packages with no import; scripts nobody runs
- Tests that exercise their own inline mocks; tests outside the runner's glob (silently never run); placeholder tests
- Legacy prop channels nothing passes; feature flags whose both branches are identical
- Known false positives: endpoint handler files paired with route registrations, DI-registered services, reflection/attribute targets, files referenced by string in config or globs, storybook/e2e fixtures

## 6. Architecture

Hunt for bottleneck files everyone touches, not layer dogma.

- God registration files (DI, route tables, nav lists, standards/mapping tables) duplicated in N places
- God contexts/stores, 1,000+-line pages and controllers, entity/config files with dozens of classes
- Jobs scheduled but never registered, registrations in the wrong order, config/factory registrations tangled with plain one-liners
- For big migrations (vertical slices, new state library, framework upgrade): estimate benefit vs cost at team size; recommend "slice-first for new code, strangler for hot spots"; list the do-not-touch set explicitly

## Reviewer output contract

Each reviewer returns exactly this shape, nothing else:

```
# <Dimension> review — <repo/path>

Scanned: <dirs/files/globs actually read>   Not scanned: <what was skipped and why>

## Findings (highest severity first)

### [CRITICAL|HIGH|MEDIUM|LOW] <one-line title>
- Where: path/to/file.ext:LINE (more locations on further lines)
- Evidence: <quoted code, measured size, or query count — not a paraphrase>
- Impact: <who is affected and how>
- Fix (one line): <smallest change that resolves it>
- Confidence: certain | likely | speculative

## Not findings
<things that looked wrong but were verified fine, with the evidence — saves the verifier time>
```

Rules: no fix is applied by a reviewer; a section with zero findings is a valid result; anything without `Where` + `Evidence` is dropped before reporting; at most 15 findings per dimension, prioritised.
