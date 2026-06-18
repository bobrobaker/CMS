# Tech-debt shelf — capture what you touched, park it where the sweep finds it

**Trigger:** read when a session edits implementation code and spots deferred work it
won't do now, or when deciding where project-local deferred work belongs — distinct
from the learning loop (generalizable lessons), `docs/decisions/` (calls made), and the
roadmap (planned work).

## The gap this closes

Project-local tech-debt is mundane and non-generalizable — what the learning loop sheds
to session notes, what `docs/decisions/` doesn't record, and what an autonomous-triage
sweep can only *consume*, not create. Debt spotted while a function is open is lost by
session-end unless filed when seen: a compressed wrap summary can't re-derive a
symbol-level observation it never held.

## The discipline

A durable shelf (`docs/debt.md`) plus a chunk-boundary capture act: after a logical
chunk, one pass over the functions just edited, append each deferred item with enough
locus to act cold. Session-wrap and the dispatch sweep are backstops — the chunk
boundary is finer and catches symbol-level debt the coarser boundaries lose.

Pipe: **capture → shelf → drain**. Capture and the shelf are this discipline; draining
is `dispatch.md`'s job, two ways — the **relevance gate** (inline, by relevance, when a
bucket reopens a file the shelf names) and the **autonomous-triage sweep** (on demand,
by safety, for the long tail).

## Wiring

Code-bearing projects only — debt accrues with code written; a doc-shaped project
barely accrues any, so it can drop the shelf. Ships as `docs/debt.md` (from
`starter/debt.md.template`) plus a chunk-boundary trigger line in the project's always-on
`CLAUDE.md`.
