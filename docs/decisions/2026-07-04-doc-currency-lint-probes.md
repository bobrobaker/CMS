---
status: decided
---

# 2026-07-04 · Two doc-currency probes in the managed linter (two-headed decision doc; gated-vs-shipped)

## Question

A doc-currency audit of a downstream fork surfaced a class of drift the existing managed
checks miss: (1) a decision doc stamped `status: decided` at the top with a later appended
`## Update` that *reverses* it — a top-down reader inherits a dead verdict, yet
`check_decision_status` passes (the `status:` field is present and valid); and (2) a roadmap /
contract / decision line that calls a feature unbuilt ("not yet implemented", "not built",
"gated only on") long after the feature shipped — the opposite polarity of
`check_architecture_freshness`, which only verifies that a reference *resolves*. Both are
fleet-general (every fork accrues both drifts). Where should the mechanical backstop live, and
at what enforcement strength?

## Options weighed

- **Leave it to the tier-3 manual doc-drift audit.** Rejected as the sole home: the audit is
  cadence-based and human-driven (`method/tooling.md` tier-3), so this drift persists between
  passes. The enforcement-split doctrine in that same doc says a repeatedly-violated semantic
  rule earns a *loose mechanical shadow* at tier 1 — that is exactly this case. Tier-3 still
  owns the judgment; tier-1 now catches the egregious, greppable cases continuously.
- **Ship it as a fork-local `FORK_CHECKS` probe (as the downstream fork did for probe 2).**
  Rejected as the canonical home: `tools/lint_skeleton.py` is vendored into every fork and
  `bootstrap.sh --update` overwrites fork edits to it, so a fork-local copy neither propagates
  nor survives an update. Both probes benefit every fork → they belong in the managed
  `SHARED_CHECKS`, which CMS owns and re-vendors.
- **ERROR, to hard-block the drift.** Rejected — both probes rest on heuristics ("is this
  `## Update` a reversal or an addendum?"; "does this `not built` sentence refer to *this*
  symbol?"). A false positive that blocks a commit is the noise the cross-project currency
  precedent explicitly rejected. They are loose shadows of semantic rules → WARN, per the
  ERROR-only-if-unambiguously-wrong rule.
- **A third status value (`stale`) or an mtime-based freshness gate.** Rejected — the status
  vocabulary is a closed set by prior decision, and mtime currency was already rejected
  upstream as noisy. These probes read *content contradiction*, not timestamps.

## Decision

Add two WARN-only checks to the managed `SHARED_CHECKS` in `tools/lint_skeleton.py`, mirrored
verbatim into `tools/cms_lint.py`'s `CHECKS` (the "edit both together" duplication bargain,
guarded by `tools/test_lint_mirror.py`):

- **`check_two_headed_decision`** (probe 1) — flags a decision doc that is still
  `status: decided` and carries a later `## Update` whose text reverses/supersedes the verdict,
  when no reconciling supersession banner appears *above* that Update. **Deliberate partial
  supersessions are not flagged:** per `docs/decisions/README.md` a partial stays
  `status: decided` and carries an inline banner at the overturned claim — that banner above the
  Update is the discriminator that keeps the probe off it. Biased toward false-negatives
  (requires a reversing Update *and* a missing top banner *and* still-`decided` status).
- **`check_gated_vs_shipped`** (probe 2) — flags a line calling a feature unbuilt while a
  `src/…py`(`:Symbol`) reference it names resolves, or a `tool verb` code span names a
  registered argparse subcommand (`add_parser` under `src/`). Reuses
  `check_architecture_freshness`'s symbol-resolution primitive (opposite polarity). General
  across forks: a fork with no `src/` and no argparse CLI self-gates to a no-op.

The supersession vocabulary (`SUPERSEDE_RE`, `BANNER_RE`) is single-sourced in `lint_skeleton`
and imported by `tools/backfill_decision_status.py`, so the banner grammar the linter and the
backfill helper key on cannot fork.

## Rationale

Tier-1 is the right home because the drift is continuous, not cadence-shaped, and a greppable
shadow catches the egregious cases cheaply — exactly the "tighten the mechanical shadow when a
semantic rule keeps being violated" corollary in `method/tooling.md`. WARN, not ERROR, because
both are heuristic shadows of judgment rules; a false block would be the currency noise prior
decisions rejected. Reuse (the arch primitive; the single-sourced banner vocab) keeps the two
copies honest and the resolution logic un-forked. The false-negative bias means the probe stays
quiet on ambiguous cases and defers them to the tier-3 audit, which still owns the judgment.

## Consequences

- `tools/lint_skeleton.py`: `check_two_headed_decision` + `check_gated_vs_shipped` added to
  `SHARED_CHECKS`; `SUPERSEDE_RE`/`BANNER_RE` promoted to the module's public surface.
- `tools/cms_lint.py`: same two checks mirrored into `CHECKS`.
- `tools/backfill_decision_status.py`: imports `SUPERSEDE_RE`/`BANNER_RE` from `lint_skeleton`
  instead of defining local copies (single-source).
- `tools/test_doc_currency.py` (new) + extended `tools/test_lint_mirror.py`; both wired into
  `.githooks/pre-commit`.
- `method/tooling.md` tier-3 note reconciled (the currency slice of doc-drift now has a tier-1
  backstop); `docs/decisions/README.md` notes the two-headed-doc check enforces the
  reconcile-to-top convention; `docs/DESIGN.md` enforcement bullet updated.
- On the next `bootstrap.sh --update`, forks pick up both probes. A fork that shipped a
  narrow fork-local `check_gated_vs_shipped` in `FORK_CHECKS` should drop it to avoid
  double-firing (its concern to reconcile, not CMS's).

## Supersession audit

Supersedes nothing. **Extends** the enforcement mechanism established by the cross-project
decision `2026-06-19-decision-doc-status-lifecycle-enforcement.md` (in the landing zone) and the
WS2 propagation described in `docs/DESIGN.md` — it adds checks to the same managed set rather
than changing any prior call. No existing decision doc or `DESIGN.md` verdict is contradicted;
grep of `docs/decisions/` + `docs/DESIGN.md` found no conflicting live verdict.

## Provenance

Built in a CMS session from a 2026-07-04 downstream doc-currency audit that found the recurring
drift and had already shipped a fork-local probe 2. Verified structurally against
`tools/cms_lint.py`, `tools/lint_skeleton.py`, and `tools/backfill_decision_status.py`; the two
checks pass CMS's own linter (self-gating — CMS has no `src/`, no `## Update` decision docs) and
are covered by `tools/test_doc_currency.py` (positive + negative cases) and the mirror-parity
guard.
