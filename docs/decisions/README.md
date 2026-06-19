# Decisions

Project-internal design calls, one per file, named `YYYY-MM-DD-slug.md`. Each
records the call and its *why* so a later session inherits the reasoning instead of
relitigating it. Cross-cutting calls that outlive this repo go to the cross-project landing zone
(`landing/decisions/`), not here.

Keep entries short: the decision, the alternatives weighed, the reason chosen.

## These are immutable point-in-time records

A decision doc records what was decided *and why, when*. Do **not** edit an existing
entry to reflect new thinking — that erases the reasoning a later session needs to
understand how the call evolved. The dated file is the historical record; let it stand.

When a decision changes, **supersede** rather than rewrite:

1. Write a **new** dated decision (`YYYY-MM-DD-slug.md`) stating the new call and why it
   replaces the old one.
2. Annotate the **old** entry with a pointer to the superseding decision, at the
   granularity that actually changed:
   - whole decision overturned → a **doc-level** banner at the top
     (e.g. `> **Superseded by [<date> — <slug>](<file>)**` — see
     `2026-06-14-instantiate-store-flag.md`);
   - one section/claim overturned → a **paragraph- or sentence-level** note inline,
     leaving the rest intact.
   The old entry keeps its original body below the annotation.

The **only** edit an existing decision should receive is that supersession annotation.
A Monition row fires when you edit anything under `docs/decisions/` to remind you of
this — if you're not adding a superseding decision, you probably shouldn't be editing.

(While *authoring* a brand-new entry in the same change, normal drafting edits are fine —
the rule guards *landed* decisions, not the one you're currently writing.)

## Status frontmatter — retirement is visible at the file

Every decision doc carries YAML frontmatter `status:` from the **closed set
`decided | superseded`**, so a cold session reading the file knows whether it's still in
force without cross-checking the verdict registry (`docs/DESIGN.md` here; `road.md §2` in a
fork). The linter (`tools/cms_lint.py`, and `tools/lint.py` in a fork) **ERRORs** if a
decision doc is missing `status:`, carries a value outside the set, or is `superseded`
without a resolvable `superseded_by:`. The check is depth-robust — it covers a `decisions/`
dir at any depth under `docs/` — and self-gates (a repo with no such dir is never burdened).

```
---
status: decided
---
# 2026-06-01 · …
```

- **`status: superseded`** means **whole-doc dead**, and requires
  `superseded_by: <sibling-file.md>` pointing at the successor. Keep the doc-level banner too
  (see above) — the field is the machine-checkable bit, the banner is the human pointer.
- **Partial supersession stays `status: decided`.** A doc that's only superseded *in part*
  (one section/claim overturned) is still live for the rest, so a session should still read
  it — it keeps `status: decided` plus the inline paragraph-level banner.
- **Reversal with no successor is a convention, not a third status value.** If a decision is
  *reversed* (not replaced by a refined call), record the reversal as its **own new decision
  doc** and point the reversed file's `superseded_by:` at it. The set stays
  `{decided, superseded}` — there is no `reversed`/`retired`/`obsolete` value; everything dead
  is `superseded` with a `superseded_by:` that explains why.
