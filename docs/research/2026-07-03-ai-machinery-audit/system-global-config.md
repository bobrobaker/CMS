# System lens — global harness configuration (~/.claude)

Snapshot: 2026-07-02/03. Paths home-relative; the config itself is symlinked into a
private dotfiles repo for version control.

## settings.json

- Model: `opus[1m]` pinned in settings.json (1M context window); Fable 5 sessions run
  via session-level model choice, not the settings pin. (Corrected 2026-07-03 — the
  original mapping pass misread this value.)
- Env: `CMS_LANDING_ZONE`, `MONITION_STORE` (hub in the landing zone),
  `MONITION_SQL_SERVER=1`, `MONITION_EMBED_DAEMON=1`, `MONITION_FIRING_OBSERVER`
  (statusline widget), `CMS_SRC` (absolute pin), `SPAWN_STAGE`.
- Permissions allow-list: `Bash(python3*)`, `Bash(python*)`, `Bash(monition *)` —
  tight scripting whitelist.
- Hooks: SessionEnd → `~/.claude/cms/tools/session_tokens.py`; Stop →
  `~/.claude/cms/tools/autoflag.py`; SessionStart/UserPromptSubmit/PostToolUse/
  PostToolUseFailure/PermissionRequest → notify shim (`$SUPERSET_HOME_DIR` unset, so
  these are fail-open no-ops).
- Statusline: custom `statusline.py` (382 lines: context bar, memory, cache TTL, I/O
  ratio, monition count, flag queue), 60s refresh; `statusline_flag.py` observer with a
  newly added 14-day opportunistic reaper (uncommitted at snapshot time).

## Skills — 23 global, all symlinked, none dead

- **From dotfiles (7):** agents-view, catch-me-up, confer-overwatch, confer-run, learn,
  relay, spawn.
- **From CMS (16):** the CMS skill set (see [system-cms.md](system-cms.md)).
- No name collisions, no broken symlinks. Project-scoped duplicates exist in sibling
  repos but global symlinks point at CMS canonically.

## Agents

One custom agent: a PM-overwatch/adviser definition for the landing-zone vault (no
model override). Candidate for Claude Code's per-subagent persistent memory
(`memory:` frontmatter) now that it exists first-party.

## Daemon

Healthy: supervisor running (v2.1.197 at snapshot), lock/status current, background
spawns claimed and settled, spare worker pool maintained, no recent errors, 52K log.

## Accumulation without a consumer (the real findings of this lens)

| Path | Size | State | Suggested policy |
|------|-----:|-------|------------------|
| tool_trace.jsonl{,.1} | 10.9M | orphaned — tool_logger unwired 2026-07-02 (clean retirement; script kept for re-wiring) | delete files |
| session-env/ | 7.7M | 1,921 empty UUID dirs, stale since mid-June, no consumer | confirm harness ownership, then delete |
| jobs/ | 36M | active accumulation, no cleanup policy | 30-day TTL for completed jobs |
| file-history/ | 46M | unbounded, one entry per edited file per session (~4,566 session dirs) | 90-day TTL |
| logs/sessions* | ~6M | session archive + index, unbounded | TTL or size cap |
| paste-cache/ | 132K | clipboard snapshots, no TTL | 7-day TTL |

Total `~/.claude` at snapshot: ~937M. Not alarming, but several stores have runaway
shape over a 12-month horizon. The flag-reaper's opportunistic-TTL pattern is the
template to copy.

## flag-corpus.json

14K / 530 lines; seed corpus for the autoflag lexical layer (~20 admitted-error
phrasings + ~510 weighted conversational admissions); read by the Stop hook, grown only
at mine-time. Healthy and current.

## Global CLAUDE.md

163 lines / ~11K (~4–5K tokens per session). Lean and decision-boundary-focused; no
filler found. Within Anthropic's June 2026 ≤200-line guidance. Minor edits
(simplifications) uncommitted in dotfiles at snapshot.

## Single points of failure

1. **`~/.claude/cms` symlink** → the CMS checkout: if it moves, Stop and SessionEnd
   hooks break. Acceptable (repo pinned, version-controlled); revisit if CMS ever
   relocates.
2. **`monition` CLI on PATH** — statusline widget and hooks degrade gracefully if
   broken (fail-open verified).
3. **Landing-zone path pins** (`CMS_LANDING_ZONE`, `MONITION_STORE`) — breakage
   requires moving the vault; low risk.

## Sibling-repo lifecycle check

- **ai-workflow-lab:** wound down deliberately — README retirement banner added
  2026-07-02 ("no active development since 2026-05-01"). Not abandoned-by-accident.
- **agent-harness:** actively developed (commits within 48h of snapshot: spawn status
  verb, unattended permission policy, tmux worker backend, review/land/close/status
  subcommands). Powers the interactive-agent sessions visible in daemon logs.

## Verified against known anti-patterns

- Stop-hook infinite loop: `autoflag.py` checks `stop_hook_active` (line 115) and never
  exits 2 — clean.
- Hook exit-code semantics and stdout hygiene: hooks here are fail-open notify/log
  shapes, not blockers — the documented exit-code-2 and stray-stdout pitfalls don't
  apply to the current wiring.
