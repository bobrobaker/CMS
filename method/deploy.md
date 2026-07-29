# Deploy — wiring the machinery into a repo with one skill

**Trigger:** read when deploying the CMS machinery into a repo (a fresh fork or an existing
project), or when editing the deploy path — `bootstrap.sh`, `tools/deploy_settings.py`, or the
`/deploy` skill. The operative artifacts are `bootstrap.sh`, `tools/deploy_settings.py`, and the
`deploy` skill.

## The shape: deterministic installer, judgement-driven driver

Deploy splits along the same line as the [enforcement tiers](tooling.md): what a script can
decide, a script decides; what needs judgement stays with the agent.

- **`bootstrap.sh` owns the deterministic primitives** — preflight the base dependencies (git,
  Python ≥ 3.10, network reachability when it must fetch the package), install the `monition`
  CLI (with the `[mcp]` extra by default, since the registered MCP server is dead without it, and
  `[wire]` unconditionally — pymysql, tiny and pure-python, a guarded fail-open transport to the
  resident Dolt sql-server that's a no-op on a SQLite store; monition
  `docs/decisions/2026-07-02-wire-client-extra.md`; `--embed` adds the semantic extra), verify the
  installed CLI with a version/capability
  handshake (a stale package that predates `init-store`/`instrument` fails loudly up front, not
  as an opaque argparse error mid-run) and make it invocable on the *current process's* PATH
  (prepending the actual install bin dir; `--fix-path` only persists it to the shell rc), arm
  the git pre-commit, create-or-join the takeaway store, merge hooks, write the MCP approval,
  and `--doctor` (a read-only health check). Each is idempotent and re-runnable — the store
  step always reaches the idempotent `monition init`/`instrument`, so a re-run heals a partial
  deploy. None of them needs to look at the repo and *decide* anything.
- **The `/deploy` skill owns the judgement** — which it can't put in bash: is this target a CMS
  fork (deploy in place) or an arbitrary existing repo (apply-to-target)? Does it already have a
  `.claude/settings.json` whose hooks must be merged, not clobbered? What do the `doctor` results
  mean, and which of the residual failures are mechanical-and-safe vs need the human?

The skill is the **single entry point** a forker runs after cloning. It calls `bootstrap.sh` with
resolved arguments, reads `--doctor`, and walks the human through the few steps that are
irreducibly interactive (trust decisions, PATH edits, hub choice).

## The argument surface (public flags)

The skill and `bootstrap.sh` share these. The flags are public; the *values* a deployer passes
encode their own setup (a hub path, whether to approve MCP) — so one public skill serves both an
external forker and a power user with a shared hub.

| Flag | Meaning |
|---|---|
| `--hub PATH` | join this exact takeaway-store hub (overrides the `$MONITION_STORE` env) |
| `--standalone` | force a per-repo store, ignoring any hub env |
| `--embed` | also install the semantic `[embed]` extra |
| `--no-mcp` | install the base package (skip the `[mcp]` extra) |
| `--approve-mcp` | write the project-MCP approval into `.claude/settings.local.json` |
| `--fix-path` | ensure `~/.local/bin` is on PATH |
| `--force-hookspath` | repoint an existing `core.hooksPath` that isn't `.githooks` (never done silently) |
| `--link-global` | (in-place only) symlink the shared skills into `~/.claude` |

## The procedure the skill runs

1. **Detect the target.** Is the cwd (or the given path) a CMS clone (has `bootstrap.sh`,
   `method/`, the `.claude/skills/` set)? → **in-place**. Otherwise an arbitrary repo → the
   skill runs `bootstrap.sh <path>` (**apply-to-target**). State which, and why, before acting.
2. **Resolve arguments.** Default to the `[mcp]` extra (`[wire]` always rides along too). If the deployer named a hub (or one is in
   the env), pass `--hub`; else the store is per-repo. Carry `--approve-mcp`/`--embed`/`--fix-path`
   through from the invocation.
3. **Run `bootstrap.sh`** with those arguments. It installs, arms, creates-or-joins the store,
   merges the hooks, and finishes by printing `--doctor`.
4. **Read the doctor output.** Every line is `PASS|WARN|FAIL  check  detail`. `PASS` everywhere →
   done. Otherwise triage by class (next section).
5. **Walk the interactive residue.** The things a script must not silently do: confirm the MCP
   **trust** decision before `--approve-mcp` writes it; offer the PATH edit rather than assuming
   it; surface a hub-vs-standalone choice when the env is ambiguous.

## What apply-to-target lays down — and never clobbers

Starter docs land **where the skills that consume them look**, only where absent: `CLAUDE.md`
at the root; `docs/road.md`, `docs/debt.md`, `docs/architecture.md` (the `/dispatch` and
`/update-roadmap` skills hardcode `docs/`); and `docs/prompts/workstream_bucket_generator.md`
(read by `/dispatch`'s bucket-generation step).

Consumer-owned files are guarded, not overwritten:

- `.claude/settings.json` — hooks are **merged**, never copied (next section).
- `.githooks/pre-commit` — written only when absent or when the existing file carries the
  `CMS-MANAGED-HOOK` marker (i.e. it's ours to refresh); a foreign pre-commit is left in place
  with loud merge instructions.
- `core.hooksPath` — if already set to something other than `.githooks`, it is left alone
  (repointing it would silently disable the repo's own hooks); `--force-hookspath` overrides.
- **Fork-variant skills** — a skill whose *deployed* form is monition's regen output (marked
  by a `*.fork-overrides.md` sibling in its skill dir; today only `mine-session`) is **excluded
  from the skill copy** and its authoring-only `*.fork-overrides.md` is never copied. CMS's
  canonical copy of such a skill is an authoring *source* (carries `forkgen:` strip/swap
  markers), not a deployable artifact — only monition's regen produces the domain-stripped fork
  variant. `monition sync`/`instrument` materializes it *stamped*; a raw CMS copy would be the
  wrong body AND unstamped, which pins monition's `_managed_state → edited` and makes sync
  WARN-skip it forever. apply-to-target relies on the `monition instrument` step (which runs
  after the copy) to install it; `--update` — which never reaches `instrument` — runs
  `monition sync` explicitly so a refresh still delivers currency. See
  `docs/decisions/2026-07-03-fork-variant-skills-monition-owned.md`.

Apply-to-target also records the deploying clone's absolute path as `env.CMS_SRC` in the
target's gitignored `.claude/settings.local.json` (merged via `deploy_settings.py set-env`).
`bootstrap.sh` itself never travels with the target, so this pointer is how a later recovery
run or `--update` finds it; `--update` refreshes the pointer.

## The global-archive rule (why apply-to-target doesn't just copy the hooks)

The harness hooks split by **where their state lives** — the same reason `bootstrap.sh` never
blind-copies `.claude/settings.json` (it's consumer-owned; clobbering it destroys the target's
config, so hooks are *merged*, never copied):

- `craft_reminder` reads *this repo's* `docs/` governance → always wired **per-repo**.
- `autoflag` and `session_tokens` write to a **machine-wide** store (`~/.claude/logs/`,
  `~/.claude/session-flags/`). One hook should serve every repo, so they belong in the **global**
  `~/.claude/settings.json` via the `~/.claude/cms` anchor — wiring them per-repo would have N
  hooks appending to one global log.

So `tools/deploy_settings.py wire-harness-hooks` honors the pattern: **global when applicable,
self-sufficient when not.** If the `~/.claude/cms` anchor is present (the deployer ran
`--link-global`, so the global hooks exist), it wires only `craft_reminder`. If the anchor is
absent, it falls back to wiring `autoflag` + `session_tokens` per-repo (and vendoring
`session_tokens.py`) so the repo stands alone. The deployer gets the global pattern whenever it
can actually fire, and a working repo regardless.

## What `--doctor` checks

Doctor resolves the store **the way the runtime does**: the `--hub` flag, then the target's
`.claude/settings.local.json` `env.MONITION_STORE` (what `monition instrument --store` writes —
the hooks read it in-session even when the shell env is bare), then the shell env
(`$MONITION_STORE`, `$CMS_LANDING_ZONE`). Store health is a live `monition list` smoke test
against the resolved store, not file existence — a present file with a broken CLI or schema
must not PASS. It also checks the interpreter (`python3` ≥ 3.10), the monition
version/capability handshake, and the hooks' designed silent-failure sink
(`~/.local/state/monition/hook-errors.log`): the hooks fail open and append stderr there, so
that log is the only evidence a hook ever failed. Growth alone means nothing — most of the
file is routine per-prompt accounting — so the check **ages** each failure rather than
counting them, and reports only ones recent enough to be live. An append-only log answers
"did this ever break", which latches true forever; the question worth gating a deploy on is
"is it breaking now".

## Triage classes for doctor failures

- **Mechanical-and-safe** (the skill can just fix or re-run): MCP not approved → `--approve-mcp`;
  PATH missing → `--fix-path`; hooks/store missing → re-run `bootstrap.sh`.
- **Needs a decision** (surface to the human): missing `[mcp]` extra when monition was already
  installed (a `--reinstall` rewrites their global CLI); hub-vs-standalone when the env is unset;
  any trust/approval the human owns.

A `FAIL` means the takeaway/MCP loop is broken (no rows fire, or the MCP server is dead); a `WARN`
means a degraded-but-working state (e.g. standalone store, no semantic search). The skill resolves
fails before declaring the deploy done.
