---
status: decided
---

# Craft-reminder config: multi-rule RULES table, defaults in the managed body, optional overlay

## Context

[2026-06-21-craft-reminder-fork-local-config-seam.md](2026-06-21-craft-reminder-fork-local-config-seam.md)
decided the managed-body / fork-local seam for the craft-reminder, with single-rule shapes
(`GOVERNED_PATHS` + `POINTER`) living *only* in the fork-local file, which bootstrap therefore
had to lay down on deploy/update. Implementing it surfaced two pressures: CMS itself needs
*several* pointers (method/, starter/, shared skills each carry a different reminder), and a
config file that is the sole home of required config forces a lay-down step and a
missing-file failure mode.

## Decision

Keep the seam; change the shapes.

- **Config is a `RULES` table** — rows of `{key, path, pointer}`; the most specific matching
  path wins. One mechanism covers one rule or many.
- **CMS defaults live in the managed body** (`tools/craft_reminder.py`, still in
  `MANAGED_TOOLS`), so the tool is complete with no local file present.
- **`tools/craft_reminder_local.py` is an optional overlay** — a module-level `RULES` list
  merged over the defaults by `key` (local wins), imported fail-open. Not in `MANAGED_TOOLS`,
  never touched by `--update`.
- **No bootstrap lay-down step** — obsoleted by defaults-in-body; a fork creates the overlay
  only when it wants non-default rules. (This supersedes the 06-21 doc's
  `lay_down_craft_reminder_config()` bullet.)
- **The 06-21 migration guard stands**: `update_target()` WARNs before re-vendoring a pre-seam
  `craft_reminder.py` (no `import craft_reminder_local` in its body) when no overlay exists —
  the fork's baked-in custom config is about to revert to defaults and must be re-applied in
  the overlay.

CMS's own `tools/craft_reminder_local.py` doubles as the worked example of the overlay.

## Validation

`tools/test_craft_reminder.py` (pre-commit-gated): merge-by-key with local-wins and
most-specific-path-wins, per-pointer once-per-session markers, fail-open on malformed stdin and
on a failing marker write (fault-injection). Overlay survival under `--update` is structural —
the file is not in the vendoring loop's `MANAGED_TOOLS` list.

## Provenance

Supersedes the config-shape and lay-down bullets of
[2026-06-21-craft-reminder-fork-local-config-seam.md](2026-06-21-craft-reminder-fork-local-config-seam.md)
(annotated there); the seam decision itself stands. Contract enumeration:
`docs/contracts/shared-machinery-propagation.md` lists `craft_reminder_local.py` as fork-local,
never vendored.
