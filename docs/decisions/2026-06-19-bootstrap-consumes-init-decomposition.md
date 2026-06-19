# 2026-06-19 · `bootstrap.sh` consumes monition's decomposed `init` (store-only + instrument-only)

**Decision.** Now that `monition init` decomposes into two orthogonal primitives —
`monition init-store <path> [--dolt]` (pure store creation) and `monition instrument
[--root <repo>] --store <path>` (pure instrumentation: wire hooks/MCP/skills + point
`MONITION_STORE`, create no store), with `monition init` retained as their composition —
CMS's deployment consumes the **two primitives**, not the fused `init`:

- **Stand up the hub:** `init-store <hub> --dolt`, once per machine.
- **Join a repo to the hub:** `instrument --store <hub>` per repo — hooks +
  `MONITION_STORE`→hub, **no** per-repo store.
- **Forker / standalone:** unchanged — `monition init` still gives one repo its own store
  + instrumentation (`unset MONITION_STORE` = no-hub mode).

`instrument` writes `MONITION_STORE` only to **gitignored** local settings
(`settings.local.json`) or relies on the machine-wide env `bootstrap.sh` already exports —
never the committed tree (forkable-lock). The broader deployment-strategy redesign (which
repos join, tier-0 payload, session-archive wiring, mining) layers on top once the
primitives exist; it does **not** gate them.

**Why.** The hub era needs store-creation and instrumentation separable in both
directions (stand up a store with no host; join a host with no store). Consuming named
primitives reads cleanly in `bootstrap.sh` and avoids the fused `init` littering a dead
per-repo store that hub-wired hooks then ignore. Two verbs beat subtractive
`--no-store`/`--no-instrument` flags — name an operation by what it does, not what it
omits.

**Sequencing / status.** monition owns and builds the primitives (build held at the repo
owner's steer, near-term — not gating CMS). CMS's `bootstrap.sh` rework waits on them and
can be drafted against the agreed contract meanwhile. **brain2 needs no rework** — its
fused `init` was already correct because its local store *is* the hub.

**Pointers.**
- monition's machinery decision: `monition/docs/decisions/2026-06-19-init-decompose-store-instrument.md`.
- Confer (monition↔CMS), archived in the monition repo:
  `monition/handoffs/archive/2026-06-19-confer-hub-era-deployment-strategy.md`.
- Builds on `2026-06-19-monition-hub-at-landing-zone.md` (where the hub lives).
