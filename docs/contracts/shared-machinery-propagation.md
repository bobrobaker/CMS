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

## Version stamp

- **Field (resolved, B01):** a **sha256 content hash** of the managed payload — the
  concatenation of the `MANAGED_TOOLS` files (`craft_reminder.py`, `autoflag.py`,
  `lint_skeleton.py`), computed offline (no network, no version registry). Stored in
  **`tools/.cms-version`** in the fork.
- **The verb:** `cms update` is `./bootstrap.sh --update /path/to/fork`, run from the canonical
  CMS clone. It re-vendors `MANAGED_TOOLS` + the skills, lays down the wrapper if absent, and
  rewrites the stamp. *Scope note:* the stamp currently covers `MANAGED_TOOLS` only — skills are
  re-vendored by `--update` but not yet stamped (a clean later extension of `MANAGED_TOOLS`).
- **Producer:** CMS — the canonical stamp is `compute_stamp` over the current CMS checkout's
  `tools/`.
- **Consumer:** the drift-warn check (B02) compares the fork's stamp against the canonical
  reference.
- **Coordinate care:** the stamp identifies the *managed payload*, not the fork's repo or its
  `lint.py` wrapper. A fork editing its local extensions must **not** change the stamp; only
  `cms update` changes it.

## Canonical reference resolution

How a fork locates the canonical stamp to compare against (degrade gracefully):

1. **`CMS_SRC` env (resolved, B02):** a path to the canonical CMS clone. The drift-check
   computes `_stamp_of($CMS_SRC/tools)` and compares it to the fork's `tools/.cms-version`.
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
