---
status: decided
---
# 2026-06-28 · One-skill deploy, and conditional (global-when-applicable) harness hooks

**Decision.** Forking is no longer "run `bootstrap.sh`, then fix a dozen manual things by hand."
A single `/deploy` skill is the entry point after a fork; it drives an extended `bootstrap.sh` and
supplies the judgement bash can't. The deterministic/judgement split is the governing principle:

- **`bootstrap.sh` gains deterministic primitives** — install the `monition[mcp]` extra by default
  (the registered MCP server was dead-on-arrival on the base package), `--embed`, `--fix-path`,
  `--approve-mcp` (write the gitignored `settings.local.json` MCP approval that never travels with
  a clone), `--hub`/`--standalone` store selection, and `--doctor` (a read-only health check that
  verifies the takeaway/MCP/archive loop actually works). A new `tools/deploy_settings.py` does the
  idempotent JSON surgery (`approve-mcp`, `wire-harness-hooks`) bash can't do safely.
- **The `/deploy` skill owns the judgement** — fork-vs-existing-repo detection, doctor triage
  (mechanical-and-safe vs needs-a-decision), and the interactive residue (MCP trust, PATH, hub
  choice). Canonical rationale: `method/deploy.md`. The skill is self-sufficient for execution; the
  method-doc pointer is a depth reference (the established CMS skill convention), so no new
  cross-repo propagation is owed — the skill travels via apply-to-target / `--link-global`.

**The harness-hook call: global when applicable, self-sufficient when not.** Apply-to-target
historically wired none of the three CMS harness hooks, by design: `autoflag`/`session_tokens` write
to a **machine-wide** store (`~/.claude/logs/`, `~/.claude/session-flags/`), so they belong in the
global `~/.claude/settings.json` via the `~/.claude/cms` anchor — not duplicated per repo. That
exclusion is correct *when the global anchor exists*. It breaks for a forker who ran apply-to-target
without `--link-global`: they get neither the global hooks nor per-repo ones.

So `wire-harness-hooks` now **detects the `~/.claude/cms` anchor** and chooses: anchor present →
wire only `craft_reminder` (per-repo by nature; the global archive hooks own the rest); anchor
absent → also wire `autoflag` + `session_tokens` per-repo and vendor `session_tokens.py`, so the
repo stands alone. This is not "abandon the global pattern" — it *honors* it whenever it can fire,
and falls back only when it can't.

**Why.** Two reasons this isn't A-xor-B (per-repo everywhere vs global-only). (1) The global pattern
is strictly better where applicable — one hook, one machine-wide store, no N-way append races — so
we keep it for the author and any `--link-global` deployer. (2) But "wired means wired" must hold for
an external forker with no global anchor, or the takeaway loop silently doesn't run for them. The
anchor's presence is the exact, observable signal that distinguishes the two, so the deploy path
keys on it rather than forcing one choice on both audiences.

**Why not just copy `.claude/settings.json` in apply-to-target?** It's consumer-owned config — an
arbitrary repo may already have its own hooks/permissions/MCP servers. Blind-copy clobbers them. So
every hook is *merged* by exact-command identity (`deploy_settings.py`), never copied — the same
merge-not-clobber discipline `monition instrument` already uses for its own three hooks.

Supersedes nothing; extends the deploy path established by
`2026-06-19-bootstrap-consumes-init-decomposition.md` and the global-archive anchor of
`2026-06-18-session-archive-tooling-global-anchor.md`.
