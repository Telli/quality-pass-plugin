# Structural refactor recipes (Phase 2, step 5)

All recipes are mechanical: same behavior, same tests, same registration order. If a test fails, the change altered behavior — fix the change.

## God registration file → per-feature extensions

1. Dump the current registration list in order (grep `Add`/`Map`/`register` calls) to `before.txt`, normalized (trim, sort only if order is proven irrelevant for that group).
2. Move only the plain one-liners (`AddScoped<IFoo, Foo>()`, `MapGroup(...)`) into per-feature extension methods. Leave config-bound, factory, decorator, and order-sensitive registrations (pipelines, executor loops, channel chains, middleware order) in place with a comment saying why.
3. Dump `after.txt` the same way; `diff before.txt after.txt` must be empty apart from moved lines.
4. Boot the runtime (or run the DI validation test / `ValidateOnBuild`) so the object graph is actually resolved once.
5. Commit with the diff of the two lists in the message.

## N hardcoded nav/route/mapping lists → one manifest

1. Find every list (sidebar, route table, breadcrumbs, permission map, feature-flag map, standards mapping). Record each entry's fields.
2. Build one typed manifest that is the superset; generate each old list from it with a selector function.
3. Snapshot-test the generated lists against the old literals before deleting the literals.
4. Delete the literals; keep the snapshot test only until the next release, then remove it.

## Giant page → page + typed pass-through components

1. The page keeps **all** state, hooks, handlers, queries, mutations. Nothing moves.
2. Each tab/modal/panel becomes a component whose props are exactly the values it reads. JSX is copied verbatim; only the prop plumbing is new.
3. Pass whole query/mutation objects with minimal structural types (`{ isPending: boolean; mutate: (x: T) => void }`) so `isPending`-style reads stay identical and no derived flags are invented.
4. Run the page's existing tests unchanged. Then type-check with the strictest config the repo has.
5. If a component needs state the page did not have before, stop: that is a feature, not a split.

## Giant service/controller → façade + focused services

1. Group methods by the aggregate they own (e.g. Program/Plan/Finding). Groups that share private helpers stay together.
2. Extract groups into focused classes; keep the original interface as a thin façade delegating one-to-one so callers do not change in this commit.
3. Move callers to the focused services in later, unrelated commits (strangler).

## Seeder / fixture monolith

Prefer partial-class or module-per-section files sharing one context and one terminal save. Extract shared IDs into a constants module. Never introduce per-section saves — it changes transactional behavior and ordering.

## What is deliberately NOT a recipe

- Big-bang architecture migrations (layered → vertical slices, REST → GraphQL, state-library swaps)
- "Finishing" a half-done migration when the remaining cases have a real reason to be different (e.g. resource-membership checks a flat permission attribute cannot express)
- Splitting a file that nobody touches — churn without merge-conflict relief is cost only
