# Bucket [B02]: Drift-warn check — fork stamp vs canonical, self-gates disconnected

Parent: ../workstream.md
State: done
Goal for session: A check that WARNs when a fork's vendored stamp is behind canonical.
Target duration: 20 min
Context budget: Read parent + this bucket + required touchpoints only.

## Conceptual mapping

- Single concern: read the fork's stamp, locate canonical, compare, WARN or stay silent. Lives
  as a check in the vendored lint unit — same surface family as B01 but a distinct, additive
  function.

## Data contract / provenance

- Inputs: the **version stamp** (B01's output) and the **canonical reference resolution** order
  — read `docs/contracts/shared-machinery-propagation.md §"Version stamp"` and
  `§"Canonical reference resolution"`.
- Outputs: a WARN line (advisory, never ERROR) when `stamp < canonical` and canonical reachable.
- Validation: see contract `## Validation` (silent when equal; silent when disconnected; WARN
  when behind).

Report first (contract check): which resolution step applies in the test env; confirm fail-open
behavior.

## Tasks

- [ ] Add a drift-warn check to the vendored lint unit: resolve canonical, compare stamps, emit WARN if behind.
- [ ] Self-gate: no canonical reachable → emit nothing, exit non-error.
- [ ] Wire it into the lint run as a WARN-tier check (does not block pre-commit).

## Required touchpoints

- `docs/contracts/shared-machinery-propagation.md  §"Version stamp", §"Canonical reference resolution", §"Validation"`
  The interface this check consumes.
- `tools/lint_skeleton.py  grep -n "WARN"  warn-tier emission pattern`
  Match the existing WARN reporting convention.
- `B01_propagation-mechanism.md  grep "## Updates", then read from that offset`
  Handoff: the final stamp format/location B01 chose.

## Conditional touchpoints

- `bootstrap.sh  grep -n "MONITION_SRC"`
  Read only if canonical-via-local-checkout resolution needs the configured-source path pattern.

## Design direction

- **Fail open to silence, not noise** (cross-bucket invariant): any error locating canonical →
  treat as disconnected → silent. Never let drift-detection break a lint run.
- WARN, not ERROR — drift is advisory; the fork chooses when to `cms update`.
- Do not re-implement path resolution; reuse the resolution order the contract specifies.

## Validation

- Scratch fork at canonical → run lint → no drift WARN.
- Hand-edit the fork's stamp to an older value, canonical reachable → run lint → drift WARN
  present; `cms update` clears it.
- Make canonical unreachable (unset source, no network) → run lint → no drift WARN, no error.

## Done criteria

- [x] Tasks complete.
- [x] Validation passes (all five cases).
- [x] Bucket `Updates` records discoveries/gotchas/handoff.
- [x] Parent workstream progress updated.

## Updates

- [2026-06-19 14:30] Created. Handoff: none yet. Gotchas: none yet.
- [2026-06-19 15:20] Done + validated. Added `check_stamp_drift` (a **repo-level** managed check) to `lint_skeleton.py`: reads `tools/.cms-version`, resolves canonical via `CMS_SRC`, compares `_stamp_of(canonical/tools)`. WARN if behind; self-gates to silence when no local stamp or `CMS_SRC` unset/missing. Wired via a new `REPO_CHECKS` list in `run()` (runs once, not per markdown file).
  - **Validated 5 cases:** matched=clean, tampered=WARN, disconnected=silent, re-vendor=clean, no-stamp=silent.
  - **Gotcha (cross-language duplication):** the stamp algorithm exists twice — bash `compute_stamp` (bootstrap.sh) and python `_stamp_of` (lint_skeleton.py) — kept byte-identical (concat `MANAGED_TOOLS` in order, sha256). Both carry a cross-reference comment. **Changing the managed set means updating BOTH `MANAGED_TOOLS` lists**, or every fork falsely drifts.
- [2026-06-19 16:00] **Reworked (confer impl-review) — duplication removed.** `check_stamp_drift` now reads canonical's committed `tools/.cms-manifest` (via `$CMS_SRC`) and **string-compares** to the fork's `tools/.cms-version` — no python hashing. Deleted `_stamp_of`, `MANAGED_TOOLS`, and `import hashlib` from `lint_skeleton.py`; `MANAGED_TOOLS` now lives only in bootstrap.sh (single source). Message changed "behind" → "differ from" (don't assert a direction the check didn't verify — review finding 6). `CMS_SRC` documented in `method/tooling.md`; its global-settings entry is pending the user (self-mod guard). Validated: in-sync clean, tampered→WARN, disconnected→silent.
