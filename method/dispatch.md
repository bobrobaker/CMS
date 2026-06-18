# Dispatch — work sized to one context window, delegated over typed contracts

**Trigger:** read when generating or executing workstreams/buckets, when farming work
out to another agent, or when designing a project's handoff or triage surface. The
*operative* artifact is `starter/prompts/workstream_bucket_generator.md`; this doc
holds the method behind it.

## Decomposition: roadmap → workstream → bucket

Work descends roadmap → workstream → bucket, and the unit of decomposition is the
**context window**, not the feature: a bucket is a self-contained context package one
short session can execute without reading anything the bucket doesn't name.

**When not to decompose:** a phase that fits one session executes directly against the
roadmap phase's Design and Validation sections — no workstream, no buckets. The bucket
apparatus exists to package context *across* sessions; below that threshold it is
ceremony. Decompose only when the work exceeds a session or a later session must
inherit its state. (The roadmap phase's written constraints are still load-bearing in
the direct path — they are what keeps a one-shot from regressing to the genre default.)

**Sizing signals.** "Fits one session" is a judgment; make it with explicit signals
rather than optimism. Treat the work as **large** (decompose, or bridge to a fresh
session) on any one **strong** signal, or on two or more **weak** ones:

- *Strong (large alone):* a structural keyword in the ask — *split / extract /
  migrate-all / move-all / one-file-per-X*; a multi-phase classify→migrate→validate
  ordering; a new structural artifact required (module layout, registry, shim, manifest).
- *Weak (large if 2+):* touches ≥4 source files (excluding tests/docs); crosses ≥2
  subsystem boundaries; unresolved classification decisions (what goes where, which
  owner); ownership ambiguity spread across files.

State which signals fired before making the call. **Small** — a single file or a tightly
coupled pair, fully specifiable up front, with no ordering dependencies and no new
structural artifact — executes directly. When the work is large *but the current
session's context is noisy* (much of it irrelevant), don't push through: write a
decision-ready handoff and start fresh, then decompose there.

**The workstream file** (parent, always-read router):

- `Progress:` line at the top — greppable state, so finding the active workstream
  costs one grep, zero file opens.
- An **execution protocol**, numbered and marked *do not change*: read workstream →
  select bucket from the index → open only that bucket → read only its required
  touchpoints → **report first** (bucket, touchpoints read, current behavior, proposed
  edits, validation plan) → edit only once the plan is clear → validate → update the
  bucket's Updates → update workstream progress.
- A **bucket index** table with state (`next/active/blocked/done/deferred/later`) and
  dependencies — sequencing lives in data, not prose.
- **Cross-bucket invariants** stated once; **deferred/non-goals** stating the negative
  scope so a session doesn't helpfully expand it.

**The bucket file:** parent link, state, one-line session goal, target duration
(~5 minutes; split if likely >10), an explicit context budget, conceptual mapping,
tasks as checkboxes, and touchpoints in **three tiers**:

- **Required** — file + line anchor or grep pattern + one line on why, so the session
  jumps to ranges instead of reading files.
- **Conditional** — "read only if X."
- **Do-not-read** — tempting distractions, with the conclusion encoded so the session
  doesn't rediscover it.

Then design direction, validation commands with expected outcomes, done criteria, and
an Updates log. **Updates discipline is two-level:** bucket Updates take everything
local; workstream Updates take only progress, sequencing changes, and cross-bucket
discoveries. Lessons land at the narrowest scope that will fire.

**Debt relevance gate.** Between reading a bucket's touchpoints and reporting, grep
`docs/debt.md` for those same paths: a match is debt in a file you're about to open
anyway, so its fix is nearly free. Surface hits in report-first with a fold-in /
sibling-bucket / leave-parked call (fold in only within the bucket's budget). This is
the capture trigger's mirror — capture parks debt while the function is open; the gate
spends it when the function reopens. Distinct from the autonomous-triage sweep: the
sweep drains the whole shelf by *safety* on demand; the gate drains by *relevance*,
inline.

The generator prompt that produces these files carries its own Updates section —
improving future generations is a routing destination for lessons, same as any
governance doc.

**Identity is the slug, not the number.** Phases and buckets are named by a stable
slug (their content-name); any number is display-ordering only. Resolve "build X" by
slug across the roadmap, the workstreams, and open handoffs — a bare number that more
than one of those schemes defines is ambiguous, so ask, never guess.

**Reconcile vocabulary against the schema before building.** When a bucket executes
from a roadmap or spec, its informal framing can name something the data model
doesn't have — a status that isn't a status, a "row" that is really a log entry.
Check the spec's vocabulary against the actual schema or code first; if they
disagree, surface the mismatch before writing code rather than silently translating
it.

## Data contracts

When one phase produces a durable artifact a later phase consumes — a dataset, a
schema, a key family, a config — the agreement is written down as a contract, not left
implicit in the producing code. Trigger: the dependency crosses a phase/bucket
boundary. Skip for localized refactors with no serialized artifact.

The contract's core sections: **producers and consumers** (a table per artifact — the
dependency graph made explicit); **versioning** with rejection behavior (raise on
mismatch, never silently skip); **per-field meaning** including coordinate system;
**provenance pointers** (who attaches them, what must never be substituted for them);
**excluded inputs** (what must *not* be consumed, and why); **validation requirements**
as a checklist the tests must cover.

Two design points carry most of the value:

- **Field names are not contracts.** A consumer that knows a field is called
  `line_number` still doesn't know what it counts — raw-file line vs. parsed-entry
  index vs. filtered index. This family of silent off-by-one substitutions is the most
  common violation, so coordinate systems are declared explicitly, and the contract
  names the **forbidden near-miss** — the plausible wrong form a future session would
  otherwise produce (e.g. "keys are `ns.name`, never `ns_name`").
- **Consume through the approved reader only** — one validation point instead of N
  ad-hoc parsers.

Buckets that touch a contracted artifact cite the relevant contract *section* as a
required touchpoint, never duplicate the contract.

## Architect → implementer

One agent — the **architect**, holding the context and owning the plan — writes a
structured task; a second — the **implementer**, cheaper and stateless — executes it
in an isolated git worktree; the architect reviews a structured result plus the raw
diff before anything touches the main checkout. The point is that **the task artifact
is a context package** and the boundary is machine-checkable.

**Task** (architect → implementer): id, `base_commit`, description, *testable*
acceptance criteria, `files_in_scope` (guidance), `files_off_limits` (hard — includes
the harness directory itself, so the implementer can't rewrite its own cage),
validation commands. **Result** (implementer → architect): status, summary, files
changed, validation results *with exit codes and output* — the architect reviews
evidence, not the implementer's claim that tests passed — issues, proposed follow-ups
(proposals only; the implementer never writes to the registry).

Design points: isolation is **structural, not behavioral** (the implementer physically
can't touch the main checkout); apply checks base-commit drift; read-only **scout**
tasks reuse the same contract for reconnaissance; capture the diff from what the
worktree *contains*, not what was committed (`git diff --binary <base> --`, not
`format-patch` — the latter silently misses uncommitted edits).

**Run-end capture is the architect's, not the worker's.** A worker persists its own
bucket's discoveries to the bucket/workstream `Updates`, and those survive its teardown —
but the two session-end disciplines, routing lessons to the store and writing the findable
archive entry, have no owner once the worker is gone. The architect, the one context that
spans the run, runs them once at the end: a single mine pass over the worker results in
its window plus the accumulated bucket Updates, and a single run-level wrap with the
workers as sub-sections. Run-level, not per-worker — a worker mining its own short slice
yields dutiful noise, and cross-bucket lessons only resolve from the full arc.

**Open direction — a critic in the loop (not yet built).** Today only the
implementer's *result* is reviewed; the architect's *plan* is not. An unbuilt
extension runs a second reasoner — a **concern/sizing critic** — against the
decomposition *before* dispatch, pressure-testing context-width, ownership ambiguity,
and source drift, with the two iterating in a bounded loop until the buckets are sized
right. This is the reverse direction from the above (critique flowing *up* into the
plan, not work flowing *down*) and needs a turn-based relay substrate the one-shot
task contract here doesn't provide. Flagged as its home when built.

## Decision-ready handoffs

What a session writes so a future cold-start session resumes without archaeology.
Governing principle: **maximize completed reversible work; surface only the
judgment.** Sections: Goal / State (*done* vs. *verified*, never conflated) / Next
actions (the first one startable cold) / Key context (decisions *with the why*;
gotchas with workarounds) / Open decision (pre-packaged: options weighed,
recommendation stated) / Pointers.

Lifecycle: one file per goal (a second handoff *updates* it); **consume, then
delete** — a handoff is session residue, never knowledge; durable lessons are
metabolized out first. A handoff open ≳2 weeks either died (delete) or quietly became
a runbook (promote it; it's no longer a handoff).

## Autonomous triage

For sweeping a backlog without supervision: triage each item **do-now vs. needs-you**,
execute the safe class, emit a decision-ready handoff for the rest. The core test:

> Auto-execute iff the action is (a) trivially reversible AND (b) mints no shared
> structure or vocabulary. Otherwise defer. Tie-breaker: defer.

Safety is a stack of guarantees, not trust: every autonomous action is one revertible
commit; the tier-1 linter gates every worker commit; one manifest records everything
(🔴 needs-you queue with a blank **Your call:** line per item · 🟢 recently-auto-filed
review feed · sweep log). Landing gates encode learned failures: land paths, never
`git merge` (live trees are normally dirty); re-stat each item before landing and skip
visibly if it changed; never resume a worker session — re-prime fresh from the
handoff; on collision, preserve the worker's branch; dry-run by default, live runs
capped until trusted.

**Backlog sources.** When a `docs/debt.md` shelf is present, the sweep reads it as a
backlog source — capture (`tech-debt.md`) fills it, triage drains it.

## Wiring

- **Minimal profile:** the handoff skill only (handoffs land in `<repo>/handoffs/`).
- **Full profile:** `docs/road.md` + the generator prompt + the dispatch skill. Add
  the task registry + worktree runner when you actually start delegating
  implementation; add the triage manifest when a backlog saturates. Contracts get a
  `docs/contracts/` dir the first time an artifact crosses a phase boundary.
