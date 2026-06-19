---
status: superseded
superseded_by: 2026-06-17-cms-forkable-refactor.md
---
# 2026-06-14 · CMS owns host instantiation; Monition exposes machinery only

> **Superseded in its instantiation framing by [2026-06-17 — CMS is a forkable reference implementation](2026-06-17-cms-forkable-refactor.md).**
> CMS no longer orchestrates deployment via `/instantiate`; deployment is fork + `bootstrap.sh`.
> The underlying boundary survives intact — **Monition owns the machinery**, **CMS owns the
> discipline**. Kept as a point-in-time record.

**Decision.** Ratify the boundary the Monition module codified: standing the
context-management system up in a host project — deploy/dogfood — is CMS's
instantiation job. CMS owns the host-facing surface (tier-0 payload, session-archive
wiring, mining discipline, lesson-routing). Monition owns and exposes the machinery
(`init`/`sync`/`migrate`, the store contract) but does **not** orchestrate
deployment. A Monition session handed a deploy/dogfood request routes it to CMS
(`/instantiate`, or manual payload adoption for an existing host).

**Why.** Both repos were plausible homes for "stand the system up in a project."
Splitting on *machinery vs. orchestration* keeps each repo's change surface coherent:
Monition evolves the store without owning N host wiring layouts; CMS evolves
instantiation without forking store internals. Mirrors the eval-substrate seam
already settled (Monition owns the row-coupled substrate; CMS owns the discipline).

**Owner + channel.** Canonical owner: **CMS** (this file). Propagation channel:
Monition's CLAUDE.md cites this decision; the mirror-back sweep is how future
Monition-side restatements reconcile against it. (User-accepted Monition-side
2026-06-13; ratified here 2026-06-14 via the sweep — confer not required, the user is
the shared owner of both repos.)
