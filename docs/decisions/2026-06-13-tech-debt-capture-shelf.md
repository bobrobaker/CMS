---
status: decided
---
# 2026-06-13 · Project-local tech-debt capture → durable shelf

**Decision.** Adopt a discipline for capturing *project-local* tech-debt (deferred
refactors / architecture concerns / "fix later") into a durable, tracked shelf —
**into the full/implementation payload tier only**, not minimal, not universal. The
pipe is `capture(new) → shelf(new) → dispatch-triage sweep(exists, the consumer)`. It
is distinct from the learning loop (generalizable lessons) and `docs/decisions/` (calls
made). *Decided here; **built and verified 2026-06-14** — the four artifacts
(`method/tech-debt.md`, `payload/debt.md.template`, the `payload/CLAUDE.md.template`
full-profile capture trigger, and `dispatch.md`'s shelf-as-backlog sweep) landed
through the "never codify silently" gate.*

**Shape of the artifact (binding on the build).**
- The **firing pair is primary**: (a) a durable tracked shelf (TaskCreate-equivalent or
  tracked file) and (b) a capture act that appends to it. Any `method/` doc states only
  the trigger and points at the firing artifact — never prose-as-discipline.
- **Trigger granularity:** the **chunk boundary** is primary (one pass over the
  functions just edited); session-wrap and dispatch-sweep are backstops.

**Why.** The seam is real and unowned, verified against the code: `learning-loop.md`
keeps only *reusable + non-obvious* lessons ("routine work does not qualify");
`docs/decisions/` records calls *made*, not concerns *deferred*; autonomous-triage
*sweeps a backlog that already exists* (and its registry isn't shipped at tier 0);
Monition is out of scope by the same reusable/non-obvious filter. Nothing captures
project-local debt at the moment it's seen.

**Alternatives weighed.**
- *`method/` doc as the primary artifact* — rejected: it's this repo's signature
  failure mode (material-shaped additions regress to the doc-genre default; ship the
  thing that fires).
- *Universal or minimal-tier* — rejected: evidence is n=1 on an implementation-heavy
  project; debt accrual scales with code written, and a doc-shaped project (this
  incubator) barely accrues any — which is why the gap was invisible from inside CMS.
- *Fold capture into dispatch's autonomous-triage* — rejected: triage *consumes* a
  backlog; it presupposes one exists. Capture *creates* it. They are complementary ends
  of one pipe, not substitutes.
- *Boundary-at-wrap capture only (drop the finer chunk trigger)* — rejected on
  evidence: 11 of 13 live reference `[SUGGESTION]`s are symbol-level observations
  (e.g. an `id()`-based scorer identity, a flag no caller sets) makeable only with the
  function open, which a compressed session-wrap summary **structurally cannot
  re-derive**. The finer trigger earns its standing cost.

**Reference pattern.** The domain-stripped reference is an active-obligation loop — a
suggestion/task surface that parks a deferred item and re-surfaces it when relevant; CMS
owns the build.
