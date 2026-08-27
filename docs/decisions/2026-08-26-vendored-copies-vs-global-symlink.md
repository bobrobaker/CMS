---
status: decided
---

# Frozen vendored skill copies stay; the staleness class is closed by a deploy-check
# enumeration, not by changing the distribution mechanism

## Context

The canonical corpus distributes shared skills two ways at once, and the two have opposite
currency behavior:

- **The global symlink farm** (`bootstrap.sh --link-global`) points `~/.claude/skills/<name>`
  at the canonical skill dir. It auto-tracks: editing canonical is the deploy.
- **Vendoring** (`vendor_skills()`, invoked by apply-to-target and `--update`) `cp -R`s skill
  bodies into each bootstrapped repo. It is a **snapshot**: nothing refreshes a vendored copy
  until someone re-runs `--update` against that repo.

So every canonical skill edit instantly creates drift between one auto-current instance and N
frozen ones. This was not hypothetical: a skill edit that added a whole new step to `/flag`
shipped to canonical and to the symlink, while ten manifest-bearing repos sat on bodies frozen
at their last fleet vendor ten days earlier — and the deploy check run at the time passed,
because it verified canonical, symlink, and decision-record surfaces and never enumerated the
vendored population. Three skills had drifted fleet-wide by the time anyone looked.

A second fact reframes the severity. **A global skill shadows a same-named project-local one**
— verified by probe, not inferred: a project-local skill carrying a sentinel description lost
the name collision to the global copy, while a uniquely-named project-local control skill in
the same repo was discovered normally. Consequence: on a machine where `--link-global` has run,
every vendored copy is *inert* — the author has been running canonical bodies all along. The
frozen copies are load-bearing only where the farm is absent: a forker's machine, or a repo
used without the global link.

## Call

**Keep both channels as they are.** The deploy-check amendment is sufficient; the distribution
mechanism does not change. Specifically:

1. **`/deploy-check` enumerates the vendored population** on any canonical-skill change:
   discover manifest-bearing repos via `tools/.cms-skills-manifest`, diff each changed skill
   against canonical, and report every stale instance as its own `✗` with
   `./bootstrap.sh --update <repo>` as the fix. Enumerate — never sample one repo and
   generalize. Fork-variant skills (a `*.fork-overrides.md` sibling) are excluded: their
   currency is the regen probe, not this diff.
2. **The severity is stated with the check**, so a `✗` list is not over-read. Stale vendored
   copies are a real propagation defect for forkers; they are *not* evidence that a skill's
   behavior never ran on the author's machine. Attributing a missing behavior to staleness
   without ruling out an env toggle or hook is the mistake this clause exists to prevent.

## Why not the alternatives

- **Symlink the forks instead of vendoring.** Breaks the product: a fork must be
  self-contained and survive being cloned to a machine with no canonical checkout. A symlink
  into an absolute path on the author's disk dangles there. Vendoring is a snapshot *on
  purpose*.
- **Auto re-vendor on every canonical edit (a hook).** Writes into N repos as a side effect of
  editing one, landing unreviewed changes in other repos' working trees and dirtying them
  mid-session. The blast radius is worse than the drift, and it collides with the existing rule
  that a re-vendor can clobber fork-local config in a managed tool's body.
- **A staleness check in the linter or pre-commit.** Wrong layer: the linter is per-file and
  repo-local, and pre-commit would stat every sibling repo on every commit. Drift is a
  *deploy-time* property, so the deploy-time pass owns it.
- **Drop the vendored copies now that global shadows them.** Only true on a machine with the
  farm. The vendored copy is precisely the forker's copy, which is the audience the corpus
  exists for.

## Residual

Currency is still *pull*-based: a stale fork is detected only when someone runs the check. The
accepted bound is that the check now fires on the change that creates the drift, at the moment
it is created, which is the earliest point the information exists.
