# Landing zone

Context that outlives any single repo — cross-cutting design decisions and handoffs
whose scope crosses projects — lands here, not in a project's own tree. This keeps
cross-project memory in one resolvable place instead of scattered across repos.

## Resolution

Tools and skills resolve the landing zone in this order:

1. **`$CMS_LANDING_ZONE`** — if set, an absolute path to your cross-project store.
2. **This in-repo `landing/`** — the zero-config fallback, so a fresh fork works with
   no setup.

Set `CMS_LANDING_ZONE` once you have a real cross-project home (a notes vault, a shared
repo). If that store uses a different internal layout, map it with a thin **personal**
config kept out of this repo — the contract here stays generic and forkable.

## Layout

- `decisions/` — cross-cutting design calls that outlive this repo. Project-internal
  calls stay in each repo's own `docs/decisions/`.
- `handoffs/` — handoffs whose scope crosses repos. A single repo's handoffs stay in
  its own `handoffs/`.
