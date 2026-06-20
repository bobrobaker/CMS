# Bucket [B03]: Backfill scaffold — assisted-classification-with-confirmation

Parent: ../workstream.md
State: later
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

## Required touchpoints

- `tools/lint_skeleton.py  grep -n "check_decision_status"  status vocabulary + discovery glob`
  The convention this helper backfills toward (closed set, depth-robust discovery).
- `tools/cms_lint.py  grep -n "check_relative_links"`
  Inbound-link detection reuses the same link-resolution logic — do not reinvent.
- `docs/decisions/README.md  (full)`
  The conventions: partial supersession = `decided` + banner; reversal convention.

## Conditional touchpoints

- `starter/road.md  grep -n "§2\|## 2"`
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
