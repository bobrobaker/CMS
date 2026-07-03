---
status: decided
---

# Craft-reminder per-project config moves to a fork-local file

> **Partially superseded 2026-07-02** by
> [2026-07-02-craft-reminder-multi-rule-overlay.md](2026-07-02-craft-reminder-multi-rule-overlay.md):
> the managed-body / fork-local seam decided here **stands**; the single-rule
> `GOVERNED_PATHS`/`POINTER` shapes and the bootstrap lay-down step below were replaced
> by a multi-rule `RULES` overlay with defaults in the managed body. The pre-seam
> migration guard prescribed here stands and is implemented in `update_target()`.
> (Record extracted from the `spawn/craft-reminder-seam` spike branch when it was
> reaped, 2026-07-02.)

## Context

`tools/craft_reminder.py` is in `bootstrap.sh`'s `MANAGED_TOOLS`, so `./bootstrap.sh --update`
re-vendors it wholesale. But the file hardcoded its per-project config — `GOVERNED_PATHS` and
`POINTER` — as module constants, with a header literally saying "configure per project." The two
facts collide: every `--update` overwrote a fork's customized pointer with CMS's generic
placeholder. Because the *logic* was unchanged, the clobber diff looked innocuous and slipped
through. This was hit live in a real fork whose customized pointer had to be `git restore`d by hand.

This is the exact failure the WS2 (`fleet-standard-propagation`) seam already exists to prevent for
`lint.py` — a managed body re-vendored wholesale must not carry per-project config. `lint_skeleton.py`
(managed) + `tools/lint.py` wrapper with `FORK_CHECKS` (fork-local, never clobbered) is the
established pattern. `craft_reminder.py` simply hadn't been brought onto it; its config sat in the
managed body.

## Decision

Apply the **same managed-body / fork-local-config seam** to the craft-reminder. No new convention.

- **Managed (re-vendored):** `tools/craft_reminder.py` stays in `MANAGED_TOOLS`. It no longer owns
  per-project config; it carries CMS *defaults* and, at runtime, imports `craft_reminder_local` to
  shadow them. The import fails open — a missing or malformed local file leaves CMS defaults in
  place (a reminder never blocks work).
- **Fork-local (never clobbered):** `tools/craft_reminder_local.py` holds `GOVERNED_PATHS` +
  `POINTER`. It is **not** in `MANAGED_TOOLS`, so `--update` never overwrites it — exactly like
  `tools/lint.py`.
- **Bootstrap lays it down once:** `lay_down_craft_reminder_config()` writes the default local file
  *only if absent* (idempotent), called from both `update_target()` and `apply_to_target()`,
  mirroring `lay_down_lint_wrapper()`.
- **Pre-seam migration guard:** before the re-vendor overwrites an old `craft_reminder.py` whose
  config was baked into the managed body (detected by the absent `import craft_reminder_local`) and
  no local file exists yet, `update_target()` WARNs that custom config will revert to CMS defaults
  and must be re-applied in the new local file. The one-time migration cost is surfaced, not silent —
  the analogue of lint.py's legacy-frozen-copy flag-for-migration.

GOVERNED_PATHS moves out alongside POINTER because the header always declared *both* per-project;
a fork governs its own corpus (`src/`, etc.), not necessarily `docs/`.

## Why not alternatives

- *Leave config in the managed body, document "don't run --update on customized forks":* keeps the
  footgun armed; the whole point of `--update` is safe re-vendor.
- *Drop craft_reminder.py from `MANAGED_TOOLS`:* forks would never receive body/logic fixes — the
  opposite problem WS2 solved.
- *A live-imported shared module:* rejected fleet-wide in WS2 (breaks the zero-dep standalone fork).
  The vendored-body + fork-local-config split preserves zero-dep.

## Validation

Re-vendored into throwaway scratch repos:
- A customized `craft_reminder_local.py` **survives** `--update`; the managed `craft_reminder.py`
  body **refreshes** to canonical (before/after diff confirmed).
- Runtime: the hook surfaces the fork's custom pointer for the fork's governed paths and stays
  silent off-corpus; with the local file removed it falls back to the CMS default pointer.
- A pre-seam fork triggers the migration WARN and gets a default local file laid down.
- `--update` run twice preserves the customized config (idempotent). CMS linter passes.

Stamp note: `craft_reminder.py` changed, so its content hash (and the `MANAGED_TOOLS` stamp) moves —
correct, the managed body genuinely changed. The fork-local config is unstamped, like the lint
wrapper.

## Provenance

Gap-fix on the `fleet-standard-propagation` (WS2) seam established in
`docs/contracts/shared-machinery-propagation.md` (B01). That workstream is closed; the fork-local
enumeration in the contract is updated to include `craft_reminder_local.py`.
