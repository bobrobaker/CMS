# Bucket [B03]: Backfill scaffold — assisted-classification-with-confirmation

Parent: ../workstream.md
State: done
Goal for session: A helper that proposes `status:` for legacy decision docs; human confirms.
Target duration: 25 min
Context budget: Read parent + this bucket + required touchpoints only.

## Conceptual mapping

- Distinct edit surface and mental model from B01/B02: a one-shot migration helper, not the
  propagation runtime. Groups: signal detection, worklist emission, confirmation gate, write.

## Tasks

- [ ] Detect supersession signals for each unmarked decision doc: later docs citing it (inbound relative links), the repo's registry (`road.md §2` / `DESIGN.md`), and existing inline prose banners.
- [ ] Emit a **per-repo worklist**: each unmarked doc with a *proposed* status (`decided` default; `decided` + banner where a partial-supersession signal is found; `superseded` + `superseded_by` only on a strong whole-doc-death signal) and the evidence behind the proposal.
- [ ] Confirmation gate: write nothing until a human confirms the worklist against the repo's own registry. Support per-item accept/skip/edit.
- [ ] On confirmation, write the frontmatter; re-run the decision-status check to verify.
- [ ] Land the helper as its own vendored file (e.g. `tools/backfill_decision_status.py`) and register it in `bootstrap.sh`'s `MANAGED_TOOLS` so `--update` re-vendors it and the version stamp/manifest cover it — a function inside `lint_skeleton.py` won't do, the managed set is copied whole-file. Without this the helper ships nowhere.

## Required touchpoints

- `tools/lint_skeleton.py  grep -n "check_decision_status"  status vocabulary + discovery glob`
  The convention this helper backfills toward (closed set, depth-robust discovery).
- `tools/lint_skeleton.py  grep -n "check_relative_links"`
  Inbound-link detection reuses the same link-resolution logic — do not reinvent. Reuse the
  **vendored** copy here, not `cms_lint.py`'s: this helper is part of the managed vendored set
  and must run zero-dep standalone in a fork (importing CMS-only `cms_lint.py` breaks that invariant).
- `docs/decisions/README.md  (full)`
  The conventions: partial supersession = `decided` + banner; reversal convention.

## Conditional touchpoints

- `starter/road.md.template  grep -n "§2\|## 2"`
  Read only if registry-signal detection must parse a fork's `road.md §2` structure.

## Design direction

- **Never silent auto-stamp** (cross-bucket invariant): the default proposal is `decided`, but
  a partial-supersession signal must downgrade the proposal to `decided` + banner, and the
  human gate is mandatory — a false bare `decided` on a retired doc asserts "live," the exact
  burn. Emit the *evidence*, not just the verdict, so the human can judge.
- This helper is part of the **managed vendored set** (B01) — it propagates to forks like the
  checks do. Keep it zero-dep stdlib.
- Idempotent: re-running on an already-marked doc proposes nothing.
- Each consumer runs this once against its *own* registry — the helper is repo-scoped, never
  cross-repo.

## Validation

- Run against this repo (CMS decision docs already marked) → worklist empty (idempotent).
- Run against a scratch dir with one unmarked doc citing another → proposes `decided` + flags
  the cited doc as a partial-supersession review candidate; writes nothing until confirmed.
- After confirming, `check_decision_status` passes on the written docs.

## Done criteria

- [ ] Tasks complete.
- [ ] Validation passes.
- [ ] Bucket `Updates` records discoveries/gotchas/handoff.
- [ ] Parent workstream progress updated.

## Updates

- [2026-06-19 14:30] Created. Handoff: none yet. Gotchas: none yet. Note: this helper is what a
  downstream consumer (e.g. an unmarked backend-decision pair) runs to close its own gap — the
  concrete first consumer + its deferred follow-up eval are tracked in the landing-zone handoff,
  not here.
- [2026-06-20] Built `tools/backfill_decision_status.py` (dry-run default; `--apply` per-item
  accept/skip/edit gate; idempotent; repo-scoped via `--root`). Registered in `MANAGED_TOOLS`.
  Reuses `lint_skeleton` for the discovery predicate, frontmatter parse, and link resolution —
  extracted `is_decision_doc()` into `lint_skeleton` (+ mirrored to `cms_lint`) as the single
  source of "what the convention governs."
  **Gotcha (in-scope fix):** the vendored `lint_skeleton.check_relative_links` stripped only
  *fenced* code, not *inline* code spans, while `cms_lint` stripped both — so the vendored copy
  false-ERRORed on the backtick-wrapped banner example in `docs/decisions/README.md`, which
  would block commits in any fork carrying that README. Added a shared `strip_code()` (fenced +
  inline) to `lint_skeleton`, mirrored the sync note in `cms_lint`, and pointed the helper's
  inbound-link scan at it. Validation: idempotent on CMS; dry-run writes nothing; `--apply`
  edit→`superseded` writes a resolvable `superseded_by` and the post-write decision-status
  check passes; skip honored; both linters clean.
- [2026-06-20] **Confer with brain2 adviser** (`handoffs/archive/…-confer-b03-backfill-scaffold.md`).
  Converged; fixes built + re-validated:
  - **Pure validator (A-1+B-2):** extracted `validate_superseded_target()` into `lint_skeleton`
    (mirrored `cms_lint`), called from `check_decision_status` AND the helper's gate *before*
    writing; deleted the `ls.errors` post-write side-channel (a bad `superseded_by:` can no
    longer reach disk, and validation is a pure return not module-global state).
  - **Matcher precision (B-1):** `SUPERSEDE_RE` → verb stems (matches active voice
    "supersedes"/"replaces"); dropped the noisy bare body-prose review trigger; cited
    `docs/decisions/README.md` as the banner source-of-truth and marked the patterns advisory.
  - **Frontmatter robustness (B-3):** hardened `_FM_RE` so a closing `---` at EOF (no trailing
    newline) is recognized — fixes both the idempotency miss and the double-block insertion.
  - **Banner whole-vs-partial (B-4):** only a *top-of-doc* banner proposes `superseded`; an
    inline/deeper banner is a partial supersession → `decided` + REVIEW (never auto-assert a
    partially-superseded doc whole-dead).
  - **C parks (known choices, not built):** (1) `_frontmatter`/`_FM_RE` stay underscore-private
    though the helper imports them — safe only because the two tools co-vendor under one version
    stamp; a future de-underscore pass should make them a named public API (module docstring now
    declares the public surface as interim mitigation). (2) `_date_key` treats an undated
    successor as never-later (heuristic gap). (3) `input()` raises `EOFError` if `--apply` stdin
    is exhausted — fine for an interactive TTY, rough for piped misuse.
