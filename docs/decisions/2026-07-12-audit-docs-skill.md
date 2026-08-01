---
status: decided
date: 2026-07-12
---

# Tier-3 doc-drift audit graduates to a skill (/audit-docs) + a housekeep cadence nag (§M)

## Context

`method/tooling.md` shipped Tier 3's doc-drift / merge-candidate / always-on-leanness
slice as a manual prompt with an explicit graduation trigger: "codify that into a skill
when the project runs it a third time." The genre has now been run enough to
characterize its shape: a session-wide doc-currency reconciliation (2026-07-05, monition
— two-headed B02 NO-GO, stale roadmap body; birthed the two WARN backstops) and a
post-§L doc audit (2026-07-12, CMS `84501d9` — the WS2 fleet-propagation overclaim,
struck in place across five docs), plus doc corrections falling out of the 2026-07-03
cross-stack machinery audit. Both clean runs followed the same procedure: verify
load-bearing claims structurally, adjudicate against the declared authority,
strike-in-place, tighten a mechanical shadow when a class recurs. Nothing left to learn
by running it manually again — and a manual audit with no cadence reminder rots unrun.

## Decision

Two artifacts, the same detection-vs-resolution split as §E → `/mirror-back`:

- **`/audit-docs`** (`.claude/skills/audit-docs/SKILL.md`) owns resolution: repo-generic
  Tier-3 pass over the governed docs — summary drift/overclaims (structural
  verification, authority-first adjudication), two-headed decisions (linter WARNs as the
  worklist head), merge candidates + always-on leanness. Report-and-propose;
  consent-gated content edits; strikes, never silent deletes; recurring classes get a
  proposed WARN-only shadow rather than relitigating. Stamps
  `$XDG_STATE_HOME/cms/doc-audit.<repo>.last` on completion.
- **`/housekeep` §M** owns detection: monthly, gated on `docs/decisions/` existing,
  reads the per-repo stamp, prints one "doc-drift audit due — run `/audit-docs`" line.
  Report-only.

Per-repo stamp key because the audit is repo-scoped while the state dir is
machine-global — one repo's fresh audit must not silence another's nag.

## Scope of change

New skill dir (farm-linked; reaches forks via `vendor_skills`); housekeep §M + its
description NOT-clause; `method/tooling.md` Wiring bullet (the "still a manual prompt"
sentence would otherwise be exactly the gated-vs-shipped drift the audit hunts).

## Non-goals

Not an auto-corrector — every content edit stays consent-gated (Tier 3's own charter).
Not a replacement for the WARN backstops: the linter keeps the egregious mechanical
shadows; this pass keeps the judgment.
