# CMS Roadmap

## 1. How to use this doc

Purpose: orient sessions around project phase, history, next work, and bounded
implementation surfaces.

Current phase marker:

`<----- Ongoing phase ----->`

A **phase** is a high-level deliverable with stable interfaces. A **workstream** is a
refinable effort inside a phase. A **bucket** is a bounded implementation slice,
usually sharing files, invariants, or tests.

Each phase states: deliverable, surfaces, durable design decisions, file/doc changes,
validation, token estimate, and exit criteria. Keep details high-level enough to start
a refinement conversation, not enough to implement directly.

This file holds **active execution phases** only. The long-horizon gated/deferred
registry — items intentionally not started, gated on accumulated evidence — lives in
`docs/DESIGN.md`'s "Roadmap (forward)" section; consult it rather than duplicating it
here.

---

## 2. Phase roadmap

### Phase 1 — Audit remediation (2026-07-02)

**Status:** complete (2026-07-02, same day) — all five buckets landed and verified per
the validation criteria; exit met. Follow-ups that outlived the phase are tracked in
`docs/debt.md` (post-gate re-measurement, retention-probe age key, deferred postmortem
eval) — plus reminder row t216 (session_start) for the re-measurement checkpoint.

**Deliverable:** Land the fixes and follow-ups identified by the 2026-07-02
broad-spectrum system audit, spanning CMS, the monition repo, and dotfiles.

**Surfaces:** monition's `store.py`; the confer-family skill docs in both CMS and
dotfiles; CMS's `README.md`, `CLAUDE.md`, and `bootstrap.sh`; `session_tokens.py` and
dotfiles' `tool_logger.py`; `.claude/skills/scrutinize` and
`.claude/skills/architecture-width-scan`.

**Design:**

- **Bucket 1 (DONE) — monition `cold_start` bool("0") bug.** Fix, sweep for
  sibling occurrences of the same pattern, add a regression test. Repo: monition.
  Context: `store.py:421`'s `bool(str)` coercion made monition's report/tune output
  permanently show "0 evidence-based / 0.0% noise saved" — ground truth is ~7,828
  evidence-based decisions and ~43% suppression. This gauge feeds the gate condition
  on the Monition firing-engine item in `docs/DESIGN.md`'s Roadmap (forward), so the
  gate had been reading blind.
- **Bucket 2 (DONE) — confer-family single-sourcing.** Repos: CMS + dotfiles.
  Context: the baton/torn-write protocol is restated independently in both
  `confer-overwatch` and `confer-run`; the 2026-07-02 id-pinning hardening landed in
  one and was never propagated to the other — live cross-repo drift between two
  copies of the same protocol.
- **Bucket 3 (DONE) — CMS doc/installer fixes.** Four independent fixes:
  `README.md:67`'s stale claim of a per-repo `monition/` dir (retired in the v6
  cutover, see `docs/decisions/2026-06-19-retire-per-repo-stores-and-reference-exhibit.md`);
  `CLAUDE.md`'s provenance-scope sentence is out of sync with the actual
  `PROVENANCE_DIRS` tuple in `tools/cms_lint.py`; `bootstrap.sh`'s apply-to-target step
  still auto-tracks a forker's store dump in git, contradicting the store-stays-local
  default documented in `docs/DESIGN.md`'s "Store-stays-local hygiene" entry; and
  `--doctor` WARNs on monition's routine, expected "[capped]" info lines instead of
  treating them as healthy.
- **Bucket 4 (DONE) — test/hardening for two hook-adjacent scripts.**
  `session_tokens.py` test suite plus pre-commit wiring; `tool_logger.py` (dotfiles)
  fail-open guard. Context: `session_tokens.py` fires on every `SessionEnd`, is 388
  lines, and has zero tests; `tool_logger.py` spawns a python subprocess on every tool
  call with an unguarded `json.load` that can take the hook down on malformed input.
- **Bucket 5 (DONE) — fold `architecture-width-scan` into `scrutinize`.**
  Context: `architecture-width-scan` has had 0 invocations in 2 months; its checks
  belong inside `scrutinize` rather than as a separate, unused skill surface.

**File/doc changes:** `monition/store.py`; `confer-overwatch/SKILL.md` and
`confer-run/SKILL.md` (both repos); CMS `README.md`, `CLAUDE.md`, `bootstrap.sh`;
`session_tokens.py` + its new test file; dotfiles `tool_logger.py`;
`.claude/skills/scrutinize/SKILL.md` (absorbing `architecture-width-scan`), then
removal of the standalone `architecture-width-scan` skill.

**Validation:** a regression test pins the `cold_start` fix and covers any sibling
`bool(str)` sites found in the sweep; the two confer skill docs diff clean (same
protocol text) after single-sourcing; `--doctor` runs clean and the four doc/installer
fixes are individually spot-checked; `session_tokens.py`'s new test suite passes and
runs under pre-commit; `scrutinize` demonstrably covers the folded width-scan checks
before the standalone skill is removed.

**Estimate:** medium — five independent, agent-sized buckets.

**Exit:** all five buckets land and each is independently verified per the validation
criteria above.

---

### Phase 2 — machinery-integration eval (layer-1 canary)

`<----- Ongoing phase ----->`

**Status:** active (promoted from candidate 2026-07-03; source: the 2026-07-03 machinery
audit, `docs/research/2026-07-03-ai-machinery-audit/synthesis.md` Gap 5).

**Deliverable:** A weekly headless integration canary that programmatically asserts the CMS
machinery's cross-surface wiring is intact — bootstrap/doctor, craft-reminder injection, and
mine-session routing — and alerts when any task regresses.

**Surfaces:** `tools/` (new canary harness + per-task programmatic assertions); a committed
baseline fixture; schedule/cron wiring; exercises `bootstrap.sh --doctor`, the craft-reminder
hook, and the mine-session routing path.

**Design:**

- Three headless tasks, **programmatic assertions only — no LLM judge** (judgment-sensitive
  tasks with tolerance bands are a later increment, not this phase): (1) bootstrap a scratch
  fork → `--doctor` clean + hooks wired; (2) a session editing governed material receives the
  craft-reminder injection; (3) a synthetic mine-session routes a planted lesson to the
  expected store/kind/reach.
- Weekly cron; alert when any task fails **twice consecutively** (debounce single flakes).
- **Scope honesty:** integration canary — catches wiring/config regressions, not vendor-model
  regressions.
- **Not fleet currency:** this canary asserts a *single scratch fork's* wiring, not whether
  *existing* forks are current. Fleet machinery skew (the 2026-07-11 incident — forks running
  stale tools/skills) is detected separately by `/housekeep §L "Fork machinery skew"` (added
  2026-07-12). Don't read a green canary as "the fleet is in sync."
- **Cost control:** headless `claude -p` loads a ~21k-token prefix; strip with `--tools ""` +
  `--setting-sources project,local` (~150 tokens) — monition t107.

**File/doc changes:** new `tools/` canary harness + assertions; committed baseline fixture;
cron/schedule entry; a `docs/decisions/` record; `docs/DESIGN.md` registry update.

**Validation:** the three tasks run headlessly against the committed baseline and pass; a
deliberately-broken wiring (unwired hook) is caught before a human notices; runs are debounced
so a single failure raises no alert.

**Estimate:** medium — one harness plus three self-contained task assertions.

**Exit:** the three tasks run headlessly on a schedule with a committed baseline, and one
deliberately-broken wiring (unwired hook) is caught by the canary before a human notices it.

---

Other Phase-2+ candidates remain gated in `docs/DESIGN.md`'s "Roadmap (forward)"
section (retrieval routing maturation, Tier-3 evaluation discipline, the Monition
firing engine, warm backlog rating, store-stays-local hygiene follow-ups) — consult it
before naming the next phase.
