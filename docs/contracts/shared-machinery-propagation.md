# Contract: shared-machinery propagation (vendored copy + version stamp)

Defines the producer/consumer interface that lets a CMS-owned check reach an already-bootstrapped
fork on opt-in pickup with drift-detection, **without** breaking the zero-dependency standalone
fork. Owned by workstream `fleet-standard-propagation`; B01 defines it, B02 consumes it.

## Vendored set — which files are CMS-managed

A fork's `tools/` holds two classes of file:

- **Managed (vendored from CMS):** the portable checks CMS ships — currently the body of
  `lint_skeleton.py`'s shared checks (e.g. `check_decision_status`), the craft-reminder, the
  autoflagger. These are *replaced wholesale* by `cms update`.
- **Fork-local:** the fork's own `tools/lint.py` *wrapper* and any checks it added in the
  marked extension slot. These are **never** overwritten.

**Invariant:** the managed/local boundary is a stable seam — `--update` re-vendors only the
managed set and must leave fork-local extensions intact.

**Seam (resolved, B01).** `lint_skeleton.py` is the managed module: it exposes `SHARED_CHECKS`
and `run(extra_checks=())`. The fork's `tools/lint.py` is a thin wrapper that
`import lint_skeleton`, defines its own `FORK_CHECKS`, and calls
`lint_skeleton.run(extra_checks=FORK_CHECKS)`. Re-vendoring overwrites `lint_skeleton.py` only;
the wrapper (and its `FORK_CHECKS`) is never touched. A **legacy** `lint.py` (a pre-seam frozen
copy, detected by the absence of `import lint_skeleton`) is **flagged for manual migration, not
overwritten** — automatic extraction of fork-local checks from a frozen copy is unsafe.
`tools/craft_reminder_local.py` is fork-local on the same seam: the optional `RULES` overlay
for the managed `craft_reminder.py`, never vendored, never overwritten (see
`docs/decisions/2026-07-02-craft-reminder-multi-rule-overlay.md`); a pre-seam
`craft_reminder.py` (no `import craft_reminder_local`) gets the analogous migration WARN.

## Propagation model: managed vs overlay, down vs up

Every fork's machinery splits into two layers that behave oppositely — the split is what makes
fork deltas both preservable and classifiable:

- **Managed layer** — skills, `MANAGED_TOOLS`, method docs. Owned by canonical (CMS);
  **overwritten** on `bootstrap --update` / `monition sync`. A fork delta must never live here.
- **Overlay layer** — `craft_reminder_local.py` (`RULES`), the `lint.py` wrapper's `FORK_CHECKS`,
  `starter/` docs. Owned by the fork; **never touched** by update, and **merged on top** of the
  managed defaults (`craft_reminder`: `merge_rules(RULES, craft_reminder_local.RULES)`, local
  wins by key).

**Dissemination (down) preserves deltas** because the delta lives in the overlay, not the
overwritten managed file: an update re-vendors the managed layer and re-merges the overlay on
top. Editing a managed file directly is the anti-pattern — the next update clobbers it (the
pre-seam `craft_reminder` failure mode).

**Classifying a fork delta** is two steps. *Detection* is mechanical (`_managed_state` /
`/housekeep §L`: `untouched` = just stale → pull canonical down; `edited` = intentional
divergence → left alone, flagged). *Classification* is human, via the domain-and-environment
strip — "would another fork be wrong to inherit this?": **stays local** → an overlay;
**propagates up** → the mirror-back queue (`upstream-candidates.md` / landing-zone hub, manual;
there is **no** automatic upward sweep) → becomes canonical → flows down to all.

**Known gap:** the overlay-merge seam exists for `craft_reminder` but NOT for skills (whole-file,
no merge point). An intentionally-diverged skill has only two clean options: take canonical
wholesale, or own a fork variant via `forkgen` (author the canonical source with
`forkgen:strip/swap` markers; `monition` regenerates each fork's variant on sync — only
`mine-session` uses this today). A hand-edited managed skill with no `forkgen` is handled crudely
— `sync` marks it `edited` and silently stops updating it (open debt, `docs/debt.md`).

## Version stamp

- **Field (resolved, B01):** a **sha256 content hash** of the managed payload — the
  concatenation of the `MANAGED_TOOLS` files (`craft_reminder.py`, `autoflag.py`,
  `lint_skeleton.py`), computed offline (no network, no version registry). Stored in
  **`tools/.cms-version`** in the fork.
- **The verb:** `cms update` is `./bootstrap.sh --update /path/to/fork`, run from the canonical
  CMS clone. It re-vendors `MANAGED_TOOLS` + the skills, lays down the wrapper if absent, and
  rewrites the stamp. *Scope note:* the stamp currently covers `MANAGED_TOOLS` only — skills are
  re-vendored by `--update` but not yet stamped (a clean later extension of `MANAGED_TOOLS`).
  **[2026-07-12]** This gap bit the fleet on 2026-07-11 (a stale unstamped `mine-session` skill).
  Until skills enter the stamp, skill drift is detected out-of-band by `/housekeep §L`
  (`monition instrument --dry-run`), not by this stamp compare.
- **Producer:** CMS — `bootstrap.sh` `compute_stamp` (bash, the sole hash producer) writes the
  committed canonical `tools/.cms-manifest`; CMS's pre-commit keeps it fresh.
- **Consumer:** the drift-warn check (B02, `check_stamp_drift`) string-compares the fork's
  `tools/.cms-version` to `$CMS_SRC/tools/.cms-manifest` — it never recomputes a hash.
  ~~the canonical stamp is `compute_stamp` over the current CMS checkout's `tools/`~~
  **[audited 2026-11-03]** REFUTED — reworked per the 2026-06-19 confer (Q3), which removed the Python-side
  hash; see `docs/workstreams/fleet-standard-propagation/workstream.md` Updates.
- **Coordinate care:** the stamp identifies the *managed payload*, not the fork's repo or its
  `lint.py` wrapper. A fork editing its local extensions must **not** change the stamp; only
  `cms update` changes it.

## Canonical reference resolution

How a fork locates the canonical stamp to compare against (degrade gracefully):

1. **`CMS_SRC` env (resolved, B02):** a path to the canonical CMS clone. The drift-check
   reads `$CMS_SRC/tools/.cms-manifest` and string-compares it to the fork's
   `tools/.cms-version`. ~~computes `_stamp_of($CMS_SRC/tools)`~~ **[audited 2026-11-03]** REFUTED — no
   `_stamp_of` exists; the manifest is the reference (same rework as above).
2. *(future)* `cms update` fetching CMS's published version manifest over the network — not
   built in B01/B02; the local-checkout path above is the v1.
3. **Disconnected fallback:** `CMS_SRC` unset or its `tools/` missing → the drift-check
   **self-gates** (emits nothing, no false alarm). This degrades to no-worse-than-today; it is
   the accepted limit (identical to WS1's unbootstrapped-hook honest-dormancy). A fork re-syncs
   by running `./bootstrap.sh --update <fork>` from a fresh CMS pull.

**Invariant:** drift-detection is best-effort and must never block or error when canonical is
unreachable — fail open to silence, not to noise.

## Validation

- A fork with stamp == canonical: drift-check silent.
- A fork with stamp < canonical and canonical reachable: drift-check WARNs; `cms update` brings
  stamp to canonical and clears the WARN.
- A fork with no canonical reachable: drift-check silent (self-gated), no error.
- `cms update` run twice with no upstream change is a no-op (idempotent) and preserves
  fork-local extensions.
