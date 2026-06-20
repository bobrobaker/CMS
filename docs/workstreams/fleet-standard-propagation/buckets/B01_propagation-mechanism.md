# Bucket [B01]: Propagation mechanism — managed/local seam + version stamp + `cms update`

Parent: ../workstream.md
State: done
Goal for session: Make the vendored check-set separable, stamped, and re-vendorable.
Target duration: 30 min
Context budget: Read parent + this bucket + required touchpoints only.

## Conceptual mapping

- One mental model: "what CMS owns in a fork's `tools/`, how it's stamped, and how it's
  refreshed." All three sub-tasks edit the same surface (`bootstrap.sh` copy logic +
  `lint_skeleton.py` structure) and define the contract the rest of the workstream consumes.

## Data contract / provenance

This bucket **defines** `docs/contracts/shared-machinery-propagation.md` — read it in full.
- Outputs: the **managed/local seam** (which `tools/` files are vendored vs fork-local); the
  **version stamp** (format + storage location); the **`cms update`** behavior.
- Provenance: the stamp identifies the managed payload only — never the fork repo or its local
  `lint.py` wrapper. Only `cms update` changes the stamp.
- Validation: `cms update` is idempotent and preserves fork-local extensions (see contract
  `## Validation`).

Report first (contract check): which contract section each edit touches; what producer/consumer
boundary it sets; what a wrong stamp coordinate would break.

## Tasks

- [ ] Introduce the managed/local seam: move CMS-owned checks (e.g. `check_decision_status`) into a vendored unit the fork's `lint.py` includes/imports, leaving the fork's extension slot untouched.
- [ ] Define + emit the version stamp (pick hash vs version string; record the choice in the contract as source of truth).
- [ ] Add `cms update` as a new `bootstrap.sh` mode that re-vendors the managed set and rewrites the stamp; idempotent; never clobbers fork-local extensions.
- [ ] Finalize the contract doc's open choices (stamp format, stamp file path).

## Required touchpoints

- `bootstrap.sh  lines ~216-250 (apply_to_target)  [f -f lint.py] || cp`
  Current copy-once logic; `cms update` extends this region's model.
- `bootstrap.sh  /usage()/,  /main()/  mode dispatch`
  Where the new mode is wired alongside in-place / --link-global / apply-to-target.
- `tools/lint_skeleton.py  grep -n "def check_"  shared checks`
  The managed checks to factor behind the seam.
- `docs/contracts/shared-machinery-propagation.md  (full)`
  This bucket owns it.

## Conditional touchpoints

- `tools/cms_lint.py  grep -n "check_decision_status"`
  Read only if the seam refactor must keep `cms_lint.py`'s verbatim copy in sync.

## Design direction

- The seam is the load-bearing move: re-vendoring is unsafe until managed ≠ fork-local. Prefer
  a vendored module the wrapper `lint.py` imports, with the fork's extension slot in the wrapper.
- Zero-dep invariant: the vendored unit must be plain stdlib Python a fork runs with no CMS
  install — do not introduce an import of a CMS-only package.
- Stamp must be cheap to compute offline (content hash of the vendored payload is the safe
  default — no network, no version registry needed for the producer side).
- `cms update` resolves canonical via the contract's reference-resolution order; if canonical is
  unreachable it reports "cannot reach canonical; nothing to do" and exits 0 (no error).

## Validation

- Run `bootstrap.sh /tmp/fakefork` (or equivalent apply-to-target into a scratch dir), then
  `cms update` on it twice.
- Expected: first `cms update` writes the stamp; second is a no-op; a hand-added line in the
  fork's extension slot survives both; the vendored unit runs under plain `python3` with no CMS
  on PATH.

## Done criteria

- [x] Tasks complete.
- [x] Validation passes.
- [x] Bucket `Updates` records discoveries/gotchas/handoff (esp. the final stamp format).
- [x] Parent workstream progress updated.

## Updates

- [2026-06-19 14:30] Created. Handoff: none yet. Gotchas: none yet.
- [2026-06-19 15:05] Done + validated. **Seam:** `lint_skeleton.py` exposes `SHARED_CHECKS` + `run(extra_checks=())`; `tools/lint.py` is now a wrapper laid down by `bootstrap.sh` (`lay_down_lint_wrapper`). **Stamp:** sha256 of `MANAGED_TOOLS` (craft_reminder/autoflag/lint_skeleton) → `tools/.cms-version`. **Verb:** new `./bootstrap.sh --update <fork>` mode (`update_target`).
  - **Decisions (safe defaults, confirm if disagree):** (1) legacy frozen-copy `lint.py` → detect-and-warn, **never** auto-rewrite (manual migration is rollout/B06); (2) stamp covers the `tools/` managed set only — skills are re-vendored by `--update` but unstamped (clean later extension of `MANAGED_TOOLS`).
  - **Bug caught by the test:** `update_target` missed `mkdir -p .claude/skills` → `set -e` aborted before wrapper/stamp were written (first test run's PASSes were false). Fixed; re-test green.
  - **Validated (scratch fork):** wrapper+stamp+skills written; `python3 tools/lint.py` exits 0 with no CMS/monition on PATH (zero-dep); `--update` stamp idempotent; fork-local edit survived re-run; legacy `lint.py` detected + preserved.
  - **Handoff → B02:** canonical = the CMS clone `--update` is run from; the comparison value is `compute_stamp` over canonical `tools/`; the fork stores its stamp in `tools/.cms-version`. Drift = fork-stamp ≠ canonical-stamp.
  - **Handoff → B06:** existing forks with a legacy `lint.py` need migration — now handled by **B07** (assisted), not just manual.
- [2026-06-19 16:00] **Reworked (confer impl-review).** Stamp moved to a committed `tools/.cms-manifest` produced by `./bootstrap.sh --refresh-manifest` (bash sole hash producer), kept fresh by CMS's pre-commit. Added the `--refresh-manifest` mode. Legacy fix: `lay_down_lint_wrapper` now returns non-zero on a legacy `lint.py` and the caller **skips `write_stamp`** (don't falsely report in-sync). Validated.
