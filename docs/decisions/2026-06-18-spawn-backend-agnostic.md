---
status: decided
---
# 2026-06-18 · The spawn primitive is backend-agnostic — CMS never hard-depends on Superset

**Decision.** The agent-spawn primitive that CMS ships (the `agent-spawn`-style script
behind the `/spawn` skill, and the relay layer on top) is **backend-agnostic**: one stable
`spawn / open / list / kill` contract over pluggable backends. **Superset** is the default
*on the home machine only* — auto-detected when its CLI is present and logged in.
**tmux + `git worktree`** is the portable fallback that runs in any environment (no GUI,
SSH/phone-safe). Callers are held to the lowest-common-denominator contract; Superset-only
niceties (GUI window, host targeting) hide behind optional flags. Both backends spawn
*interactive* `claude` (no `-p`) so sessions stay on the subscription bucket, not the metered
programmatic/Agent-SDK bucket.

**Why.** CMS's identity is self-contained, works-anywhere, publishable machinery with a
bottom-up adoption model (minimal profile works everywhere; upgrade pieces only on
saturation). A hard dependency on Superset — a per-machine Electron GUI app — breaks all of
that: a forker without Superset gets broken machinery, and the "generic" payload silently
stops being generic. The user explicitly does not want CMS to "only work with Superset."
Single-sourcing one contract over swappable backends keeps the published payload honest while
still letting the author get Superset's niceties at home.

**Alternatives weighed.**
- *Superset-only spawn* — rejected: couples the publishable payload to a per-machine GUI app,
  contradicting CMS's works-anywhere identity.
- *tmux-only spawn* — rejected: throws away the home-machine GUI affordances (watchable tabs,
  host targeting) for no portability gain over a pluggable default.

**How it lands.** Keep any harness machinery destined for CMS payload behind the
lowest-common-denominator contract. The tmux+worktree substrate is the DIY fallback; the
two-agent relay ("watch them talk") is a separate backend-agnostic layer on top of spawn. The
home-machine Superset backend and its operational gotchas (socket-drive, CLI-verb churn,
forced `--json`, the interactive-worker wedge) are documented out-of-tree in the author's vault
(`brain2/20 Active/superset_handoffs.md`), deliberately **not** in CMS — keeping them here
would re-introduce the dependency this decision forbids.
