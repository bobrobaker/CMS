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
