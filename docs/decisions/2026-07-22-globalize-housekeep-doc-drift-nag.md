---
status: decided
date: 2026-07-22
---

# Globalize the /housekeep §M doc-drift cadence nag across sibling governed-docs repos

## Context

§M nagged the `/audit-docs` cadence only for the cwd repo — it read the single
`doc-audit.$(basename "$root").last` stamp for the repo housekeep happened to run
from. But housekeep runs overwhelmingly from one repo, so every *other* governed-docs
repo on the machine (8 of 9 at the time of this call) had never been nagged and so
never audited. The gap is structural: a per-repo cadence check that only fires where
you already are can never surface the repos you never visit.

Caveat for a future reader: the "8/9 overdue" figure is a **skill-age artifact** —
`/audit-docs` and its stamp were only recently introduced, so most repos had simply
never been stamped. It is not a measurement of doc rot in those repos. Don't read it
as "the fleet's docs are rotten"; read it as "the nag had no reach."

## Decision

Reuse the §L idiom in this same skill file, applied to governed-docs repos:

- **Canonical-clone gate, default ON.** `[ -f "$root/tools/.cms-manifest" ]` — same
  gate as §L. From the canonical clone, scan all sibling repos; from a bare fork,
  fall through to the original cwd-only check unchanged. Forkable-safe with no new
  required config: a fork never scans its siblings.
- **Scan root** defaults to `$(dirname "$root")` (siblings of the clone), overridable
  via `CMS_GOVERNED_ROOTS` — a new var rather than §L's `CMS_FORKS_ROOT` because the
  predicate differs (governed-docs repos, `docs/decisions/` present, including self;
  vs. forks, which exclude canonical clones).
- **Capped output.** > 2 repos due → one summary line, oldest stamp first; ≤ 2 →
  per-repo lines. Report-only in all cases — `/audit-docs` remains the separately
  invoked resolver (the §E → `/mirror-back` detection-vs-resolution split, and Tier 3's
  "reports and proposes" contract in `method/tooling.md`).
- **Duplicate-basename WARN.** Stamp keys stay basename-keyed (matching what
  `/audit-docs` writes on completion); if two scanned roots share a basename the scan
  warns instead of letting one repo's fresh stamp mask another's staleness.
- **Monthly self-gate** on the scan itself (`doc-audit-scan.last`, mtime -30 —
  mirroring §L's weekly `fork-skew.last`), so the multi-repo nag doesn't reprint on
  every daily housekeep. The per-repo 30d stamp still decides *which* repos are due
  within a due scan.

## Rejected alternative

A new env var defaulting to cwd-only (scan only when explicitly configured). Rejected
because it relocates the silent gap rather than closing it: "never run" becomes "never
configured," which never self-heals and is invisible — nothing ever tells you the var
exists or is unset. The §L canonical-clone-gated, default-ON idiom gives the same
forkable safety (bare forks stay cwd-only automatically) while making the common case
work with zero configuration.
