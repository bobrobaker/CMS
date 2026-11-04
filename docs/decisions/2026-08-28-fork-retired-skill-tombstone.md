---
status: decided
---

# Fork-side skill retirement is a tombstone sibling file that vendor_skills honors

## Context

`vendor_skills()` distributes skills by `cp -R` — a mechanism that can only ever add or
refresh. The manifest-keyed retirement path bounds *CMS-side* delete authority: a fork
skill dir is removed only when CMS itself stopped shipping it (and the manifest proves CMS
put it there). Neither path gives the **fork** a say: a fork that judges a still-shipped
skill inert for its context and deletes the dir gets it silently resurrected by the very
next `--update`, because the copy loop re-vendors anything live in CMS. The resurrection
is doubly silent when verified with `git diff --stat`, which is blind to untracked
additions.

The existing opt-out marker (`*.fork-overrides.md`) can't serve here: it lives in the CMS
*source* skill dir and routes ownership to monition's regen — it is a CMS-authored
classification, not a fork-authored one.

## Decision

A fork retires a vendored skill durably by writing a tombstone sibling file where the
skill dir lived: `.claude/skills/<name>.fork-retired` (and deleting the dir).
`vendor_skills` checks the *destination* for that tombstone before copying and skips the
skill, logging the skip. Un-retiring is deleting the tombstone; the next `--update`
re-vendors.

Mechanics that fall out without further code:

- The tombstoned skill is left out of `shipped`, so the manifest stays a truthful record
  of what *this* vendor shipped.
- The manifest retirement loop can't touch anything: its condition (c) short-circuits
  while CMS still ships the dir.
- Authority stays bounded on both sides: the tombstone is the fork exercising control over
  its own tree; CMS never writes or deletes one.

Two visibility companions landed with it: `vendor_skills` logs when a copy *creates* a
skill dir not previously present (making a resurrection or new addition loud at the moment
it happens), and `update_target` closes by pointing the operator at
`git status --porcelain` for blast-radius review.

## Why a sibling file, not an in-dir marker or a manifest entry

An in-dir marker dies with the dir the fork is deleting. A fork-edited manifest entry
would corrupt the one file whose meaning is "what CMS shipped last vendor" and would be
clobbered on the next vendor anyway. The sibling file survives the deletion, is trivially
greppable, and mirrors the established sibling-marker pattern.
