---
doctype: architecture
---
# CMS design — seams, contract, roadmap

The architecture behind the system. The README holds the story; this doc holds the
load-bearing decisions.

## What CMS is, precisely

A **forkable reference implementation**, not a generator and not an opaque package. You
fork or clone the repo and run `bootstrap.sh`; the machinery is live in *that* repo, and
the shared parts are **single-sourced** (`.claude/skills/`, `tools/`) rather than copied
per project. One canonical copy, instantly live for the author (via opt-in symlinks),
shipped unchanged to forkers — which is the opposite of the drift a copy-into-N-projects
generator accrues. The call and its why:
`docs/decisions/2026-06-17-cms-forkable-refactor.md`.

The anti-goal is the reading list: a corpus of method docs that a project would have to
*read* to benefit from. A note nobody loads is dead weight, and agents don't browse — so
every method here ships as something that *fires*: a skill, a hook, a linter check, a
prompt, a takeaway row, or a rule in the always-on doc.

## The four seams

1. **Hot ↔ cold context.** Per-file companion notes loaded by path-glob at edit time are
   *hot* context; durable concept docs retrieved on demand are *cold*. A complete system
   needs both temperatures and a promotion/demotion path between them.
2. **One closed learning loop.** Mining lessons (audits, mistake diagnosis) without a
   governed home accretes flat rule files; housing lessons without mining instrumentation
   starves the corpus. The loop is mine → house → fire, closed.
3. **Artifact and claim traceability are the same move.** Data contracts trace *artifacts*
   between pipeline phases; evidence-vs-provenance separation traces *claims* to
   re-consultable backing. Both answer "why should a later consumer trust this?"
4. **The open edge: no value model on firing.** Everything here fires on bare trigger
   match (a glob, a path, a hook, a row's `trigger_spec`). Whether a payload is *worth its
   context cost* — and how hard it should fire — needs a value model. The takeaway store
   (below) is the first step toward it; a full EV-scored firing engine is future work,
   deliberately owned by the Monition module, not this repo.

## The upstream contract

CMS is the upstream reference. A fork **drifts freely** — wires triggers to its own
workload, owns its own feedback logs. At mirror-back time, drift classifies by one rule:
strip the project's domain from the lesson. What survives is a **system learning** and
comes back upstream through the consent gate; what doesn't stays downstream as local
adaptation. Upstream docs grow gotchas and feedback layers only this way — fed by
downstream runs, on saturation, never speculatively. First landing of the mechanism:
`docs/decisions/2026-06-13-mirror-back-dispatch-and-decisions-shelf.md`; CMS's own
lessons skip the queue and route at mine-time:
`docs/decisions/2026-06-14-cms-self-lessons-route-at-mine-time.md`.

Two later narrowings define the channel as it now stands. **Row-shaped lessons no longer
use the queue** (2026-07-02): a trigger lesson goes straight into the shared Monition hub
(`reach: general`, live everywhere), so the queue carries **teaching-surface proposals
only** — `method/`, skills, `starter/`, linter. And the queue has **one canonical
location** — the landing-zone hub (`$CMS_LANDING_ZONE/handoffs/upstream-candidates.md`)
when a hub is set, so every fork's candidates aggregate in one place that both producers
(`/codify`, fork `/mine-session`) and consumers (`/housekeep` §E, the sweep) resolve;
repo-local only for a standalone forker with no hub
(`docs/decisions/2026-07-05-mirror-back-queue-canonical-location.md`).

**Exception — takeaway machinery.** The store schema, executors, and lifecycle CLI are
owned by the **Monition module** and evolve by version bump there, not by copy-and-drift.
CMS declares Monition as a dependency that `bootstrap.sh` installs (SQLite backend by
default; Dolt optional behind a seam). There is no tier-0 floor and no
adopt-from-flat-file graduation: a fork stands up a real store from session one, because
firing provenance (`git_sha`/`session_id`/`situation`) is capture-time-only and can't be
backfilled. The boundary: **Monition owns the machinery** (store contract,
`init`/`sync`/`migrate`); **CMS owns the discipline** (method, skills, the installer,
lesson-routing).

## No profiles

There is no minimal/full profile to choose and no generator to tailor one. The machinery
is single-sourced and a fork takes all of it; **delete what your project doesn't need**
(a doc-shaped project drops the dispatch/bucket apparatus; a solo project drops the
cross-repo confer skill). Adoption is still bottom-up in spirit — grow the feedback and
gotcha layers only when saturation demands — but it's subtractive from one source, not
assembled from tiers.

## Current architecture (what's live)

- **The learning loop.** `mine → house → fire`, closed: `/mine-session` (+ `/flag`,
  `/postmortem`, `/concern-review`) mine; `/codify` routes the lesson to its home (a
  Monition row, a `method/` doc, a `CLAUDE.md` rule, a file-local gotcha); matched rows
  inject as context and the linter/hooks fire mechanically. Mining capture is two-tier
  (agent self-flags; a Stop-hook backstop nets what it skips):
  `docs/decisions/2026-06-18-two-tier-autoflagger.md`, with the backstop's
  self-improving lexical layer in
  `docs/decisions/2026-06-20-self-improving-lexical-flag-backstop.md` and its
  windowed since-last-Stop scan (the flush-race fix) in
  `docs/decisions/2026-07-31-autoflag-windowed-scan.md`.
- **The takeaway store** — rows + firings live in a single cross-repo **hub**
  (Dolt-backed for us) at `$CMS_LANDING_ZONE/monition` (the hub-location call:
  `docs/decisions/2026-06-19-monition-hub-at-landing-zone.md`); host repos join it via `monition
  instrument` and keep **no per-repo store** (the former per-repo monition/ dirs were
  retired in the v6 cutover — see `docs/decisions/2026-06-19-retire-per-repo-stores-and-reference-exhibit.md`).
  A standalone forker with no hub configured still gets its own SQLite monition/ store.
  Semantics in `method/takeaway-store.md`. Load-bearing invariants: **trigger is data**
  (each row carries `trigger_kind` + `trigger_spec`; executors are dumb) and **every
  disclosure is logged + ratable** (the `firings` table is the eval substrate the firing
  engine trains against). Hooks call the guarded `monition` CLI and fail-open when it's
  absent.
- **Lesson routing** — `method/lesson-routing.md`: ordered destination tests deciding
  whether a mined lesson becomes a store row or a governance-surface edit. Evals are the
  linter for semantic artifacts.
- **Enforcement + observability** — `tools/cms_lint.py` (pre-commit, ERROR blocks / WARN
  advises), `tools/craft_reminder.py` (pre-edit reminder on governed material), and
  `tools/session_tokens.py` (a SessionEnd hook summing API usage into the session log;
  `--print` feeds wrap-up skills). The managed check set (`tools/lint_skeleton.py`, vendored to
  forks) includes two WARN-only doc-currency probes — a two-headed decision doc and a
  gated-vs-shipped detector — see `docs/decisions/2026-07-04-doc-currency-lint-probes.md`.
- **Session archive** — progressive disclosure over session history: capture
  (`/wrap-session`) writes a summary + index entry; retrieval is grep over the ladder plus
  a semantic MCP server over the summary corpus. `tools/extract_session.py` lifts
  role-labelled text from a session JSONL (fail-soft, with a `--canary` mode flagging
  unknown harness record types).
- **The landing zone** — `$CMS_LANDING_ZONE` else the in-repo `landing/` fallback, so a
  fresh fork has a zero-config home for cross-project decisions and handoffs.
- **Deploy** — one `/deploy` skill is the entry point after a fork: it drives `bootstrap.sh`
  (the deterministic installer — monition + the `[mcp]` and `[wire]` extras, hook arming, store create/join,
  hook merge, MCP approval, PATH, `--doctor` health check; JSON surgery in
  `tools/deploy_settings.py`) and supplies the judgement bash can't (fork-vs-existing detection,
  doctor triage, interactive steps). Method in `method/deploy.md`. The harness hooks wire
  **global-when-applicable** (the `~/.claude/cms` anchor present → archive hooks stay global) and
  **self-sufficient otherwise**, so a wired repo runs the loop regardless — see
  `docs/decisions/2026-06-28-one-skill-deploy-and-conditional-harness-hooks.md`. Vendoring also
  **retires**: a `.cms-skills-manifest` written into the fork's `tools/` at vendor time bounds deletion to skills a
  previous CMS vendor itself installed (fork-native skills are structurally unreachable), and
  `--update`/`--doctor` check that monition's baked regen is current with CMS's authoring sources
  so a successful `monition sync` can't ship a stale monition-owned skill — see
  `docs/decisions/2026-08-16-skill-retirement-and-regen-currency.md`. The mirror image —
  a **fork** retiring a still-shipped skill — is a fork-written tombstone sibling
  (`.claude/skills/<name>.fork-retired`) that `vendor_skills` honors, closing the
  resurrect-on-every-update hole — see
  `docs/decisions/2026-08-28-fork-retired-skill-tombstone.md`. Vendored copies are
  **snapshots by design** (a fork must survive without a canonical checkout), so every canonical
  skill edit drifts them; the currency of that population is owned by `/deploy-check`, which
  enumerates manifest-bearing repos and diffs each changed skill rather than trusting the
  auto-current global symlink — see
  `docs/decisions/2026-08-26-vendored-copies-vs-global-symlink.md`.

## Roadmap (forward)

### Landed (2026-06-20) — Workstream 2: fleet propagation of shared standards + evergreen architecture-doc convention

All buckets complete; execution in `docs/workstreams/fleet-standard-propagation/`. Shipped:
the vendored-copy + version-stamp + `cms update` + drift-warn propagation; the
assisted-confirmation decision-doc backfill; the architecture doctype + mechanical freshness
check (this `DESIGN.md` is its first conforming instance — `doctype: architecture`); and a
mirror-parity guard keeping the vendored linter honest. Fork rollout is queued (opt-in) in the
landing zone. The design call below is retained as the standing rationale.

> **[2026-07-12 UPDATE]** The mechanism landed; the *fleet* was not thereby made current. Drift
> found 2026-07-11 (stale skills across forks) traces to two in-scope-documented limits: skills
> are unstamped (see `docs/contracts/shared-machinery-propagation.md` §"Version stamp") and the
> drift-WARN is fork-local/self-gating — neither is a fleet scan. The central, skill-aware
> detection cadence is `/housekeep §L` (added 2026-07-12, commit a05e43e), which *extends* — does
> not duplicate — the mirror-parity guard. The 2026-07-12 fleet fix brought all forks current.
> See `docs/workstreams/fleet-standard-propagation/workstream.md` Progress + 2026-07-12 note.

WS1 made decision-doc retirement machine-enforced and legible at the file, but shipped the
check by **verbatim duplication** into each fork's tools/lint.py at bootstrap time. Forks
extend lint.py locally and there is no downstream sync, so a later CMS opinion change never
reaches an already-bootstrapped fork — opinion freezes at bootstrap time. WS2 closes that gap
and lands the evergreen architecture-doc convention.

**Design (decided — this is the standing call).**

- *Propagation* — **vendored-copy + version-stamp + a `cms update` re-vendor verb + a
  drift-warn check.** A fork keeps a vendored copy of the shared checks (zero-dep preserved —
  runs with no CMS install present), stamped with a canonical version; `cms update` re-vendors
  the latest; a check WARNs when a fork's stamp is behind a reachable canonical reference. A
  disconnected fork (no canonical reachable) self-gates the check — honest dormancy,
  no-worse-than-today. *Rejected:* a live-imported shared module (breaks zero-dep); a two-tier
  always-current internal path (contradicts opt-in pickup + drift-detection).
- *Backfill* — **scaffold as assisted-classification-with-confirmation**, never silent
  auto-stamp: detect supersession signals → per-repo worklist → one-pass human confirmation
  against that repo's own registry before any write. A false `decided` on a retired doc
  affirmatively asserts "live" — the exact burn WS1 exists to prevent. *Rejected:* grandfather
  (leaves the existing-fleet gap open).
- *Evergreen architecture-doc convention* — a **fleet-wide doctype** (coarse module/seam
  altitude — must express "module owns X; boundary to repo Y is here"; contract-anchored;
  index-don't-duplicate, i.e. "see road.md §2" pointers are valid) plus a **mechanical
  freshness check** (referenced paths/symbols resolve — without it "evergreen" is only a
  promise). Two distinct homes: CMS's own current-architecture stays in this `DESIGN.md`; the
  fleet-wide doctype is a *separate* convention forks adopt — "CMS uses DESIGN.md" must not
  become "everyone uses DESIGN.md."

**Validation (exit).** A fork behind canonical gets a WARN that `cms update` clears; a bare
repo stays silent (self-gated); the backfill never writes without confirmation; the freshness
check fails on an unresolved referenced path; CMS's own `DESIGN.md` validates under the new
convention (dogfood). Execution: `docs/workstreams/fleet-standard-propagation/`.

### Landed (2026-07-05) — audit item 3: Monition retro rating supply (`/housekeep` §G1)

The last open 2026-07 machinery-audit item. A weekly, cadence-gated `/housekeep` clause
(§G1) that produces `retro` relevance labels over the traffic head — an evidence-gated LLM
retro-rater consuming Monition's per-row backlog sampler (`export-firings --rows-by
unrated-priority`) and retro applier (`rate --from-export`). It feeds the existing row
audit (§G2) and the fire/suppress gate the eval data the live mine-session pass alone can't
keep up with. **Seam:** Monition owns sampler + priority order + `retro` provenance; §G1
owns cadence, budget, consent. **Rail:** retro is asymmetric training supervision only —
the held-out relevance set stays live-only; retraining on retro is deferred until volume
accrues. Unblocked by the Monition dogfood (excerpts rich enough to rate). Call + why:
`docs/decisions/2026-07-05-housekeep-retro-rating-supply.md`.

### Active (2026-07-03) — Phase 2: machinery-integration eval canary (layer-1)

The layer-1 integration canary is **built** (harness `tools/eval_canary.py` + guard
`tools/test_eval_canary.py`, wired into pre-commit): three programmatic tasks —
bootstrap→`--doctor`, craft-reminder injection, mine-session routing plumbing — at fidelity
option (B): declarative wiring assert + direct behavior assert, **no live `claude -p`**.
Rationale and the rejected fidelities (A/C): `docs/decisions/2026-07-03-eval-canary-fidelity.md`;
spec + exit: road.md Phase 2. It catches wiring/config regressions, **not** vendor-model
regressions — that judgment-band layer is the deferred **Tier-3 evaluation discipline** below,
a distinct increment *above* this one. Cadence: folded into `/housekeep` §K (the harness
`--if-due 7` self-gate), which runs it weekly and surfaces only on an alert — not a standalone
cron. See the decision doc's 2026-07-03 update.

All deferred work below shares one philosophy with the firing engine: gated on accumulated
evidence, never built speculatively.

- **Retrieval routing maturation** — an eval-governed router choosing grep vs. semantic
  search over the governance corpus, gated on retrievals-log volume.
- **Tier-3 evaluation discipline** — the judgment-band layer *above* the now-active layer-1
  integration canary (see above): evaluating governance lines / prompts / skill text by
  the *rate of a named failure mode* over production traces (the build-out of "evals are
  the linter for semantic artifacts"). CMS owns + ships the discipline (a `method/` doc +
  per-project harness, never a central service); Monition owns + exposes the row-coupled
  substrate (a versioned read-verb + the ΔP(fail) currency); the project owns its traces
  and failure-mode labels. Gated on labeled-trace volume — never day-one.
- **The Monition firing engine** (in the Monition module, not here) — the EV-scored engine
  over the store's `firings` data, replacing hand-tuned `trigger_spec`s and the manual
  rate-and-tighten loop with learned firing decisions. Collection is live; the engine is
  gated on accumulated honest ratings.
- **Warm backlog rating (excerpt-class labels)** — extend the mine-session rating pass
  to also sweep *past* sessions' unrated firings from the current warm session, judged
  from stored evidence (`trigger_context` + `match_evidence`, optionally the session's
  archive summary). Scope: noise-by-irrelevance only — a repo-steeped judge can evidence
  relevance from excerpts; helpfulness/causality it cannot, and abstains. Same
  bulk-confirm gate. Precondition: a Monition-side evidence-class tag on ratings (lived
  vs. excerpt) so the fire/suppress gate can weight label classes — unmarked mixing
  would dilute the eval substrate the warm-rating discipline protects. Gated on that
  provenance column landing; then a routing bump adds the sweep to the rating pass.
- **Store-stays-local hygiene** — the store (hub for us; per-repo for a standalone forker)
  stays local and is never published. `bootstrap.sh` apply-to-target now gitignores a
  freshly created per-repo store and ships its pre-commit dump-tracking step commented out
  (explicit opt-in: uncomment + un-ignore its `dump.sql`). One follow-up remains:
  `monition init` (in the monition repo) still advertises the old unconditional-dump
  behavior in its own scaffolding — out of scope here, align it separately. (Our hub deliberately keeps a tracked `dump.sql` in the private
  landing-zone repo for offsite backup — that's the opt-in, not the default.) Open sub-question: where a *public*-repo project's store gets backed up — since
  it's gitignored, git no longer backs it up, so a private destination is decided per
  project. (Verified safe meanwhile: the published module bundles no store data, so
  installing Monition cannot leak anyone's firings.)

## Porting rules (for anything that enters `method/` or the shared machinery)

- **Generalize, don't copy.** Keep the mechanism + one neutral worked example.
- **Show, don't claim.** Ship the artifact (a runnable hook, a real template) over a
  description of it. This repo dogfoods its own machinery for the same reason.
- **Single source.** One canonical rendering of any rule; derived views are generated,
  never hand-maintained.
- **No provenance in doc bodies.** Origins live in private git history, not in what a
  reader sees. The linter WARNs on known provenance strings.
