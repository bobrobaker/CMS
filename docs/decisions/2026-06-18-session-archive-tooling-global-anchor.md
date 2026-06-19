# 2026-06-18 · Session-archive tooling is global, anchored at a dotfile

**Decision.** The session-archive *capture* tooling (`tools/session_tokens.py`,
`tools/extract_session.py`) and the `archive/` retrieval tooling
(`recall.py`, `backfill.py`, `semantic/`) are **global machinery**, not per-project
copies. They resolve through a single dotfile anchor, `~/.claude/cms` — a symlink to the
canonical CMS clone, created by `bootstrap --link-global` (the same "this clone is
canonical" step that symlinks the skills into `~/.claude/skills/`). Every caller resolves
the tooling through that anchor:
- `/wrap-session` invokes `~/.claude/cms/tools/{session_tokens,extract_session}.py`
  (fallback `$CLAUDE_PROJECT_DIR/tools/…` for a bare in-clone run that never linked).
- The global `SessionEnd` hook in `~/.claude/settings.json` runs
  `~/.claude/cms/tools/session_tokens.py` (was a hardcoded `~/projects/CMS/…`).
- The semantic MCP server registers at `~/.claude/cms/archive/semantic/server.py`.

`bootstrap.sh` no longer copies the capture tooling into target repos (`apply_to_target`
dropped `session_tokens.py` / `extract_session.py` from its per-project copy list). Only
genuinely per-project machinery still ships per repo: the edit-time hooks
(`craft_reminder.py`, `autoflag.py`) and the linter skeleton.

**Why.** The session archive is *inherently global* — one corpus across every project,
living at `~/.claude/logs/{sessions,sessions.md,sessions-index,retrievals.jsonl}`. Its
tooling was reached three inconsistent ways: the global skill via
`$CLAUDE_PROJECT_DIR/tools/` (the *current* repo), the global `SessionEnd` hook via a
hardcoded `~/projects/CMS` absolute path, and `bootstrap` by *copying* the tools into
each target. A global skill operating on global data, reached through per-project copies,
is exactly the drift tax the forkable refactor set out to kill — it just hadn't fanned
out yet (only CMS was bootstrapped, so `/wrap-session` silently only worked from CMS). The
skills already got the single-source + symlink treatment; this extends the same model to
the archive tooling. One canonical copy, live in every repo, clone-location-independent,
forker-portable (a fork's `--link-global` points `~/.claude/cms` at *its* clone).

**Refines** `2026-06-17-cms-forkable-refactor.md`. That decision single-sourced shared
machinery and symlinked the skills; it left the archive tooling on the old copy-per-
project path. This applies the same single-source rule to the archive tooling via the
`~/.claude/cms` anchor. It does **not** reopen the generator question — the tooling lives
in the repo and is *symlinked*, never copied, for cross-repo use.

**Supersedes the wiring claim in `method/summaries.md` §Wiring & ownership** — the line
"Capture ships per-project" described the pre-anchor design and is rewritten: capture
tooling and retrieval are both global, anchored at `~/.claude/cms`; only the per-project
hooks and linter ship per repo.

**Anti-goal.** Not a new env-var convention to export and not a fourth resolution path:
the symlink *is* the configurability (repoint it to move the canonical clone). The
`$CLAUDE_PROJECT_DIR` fallback exists only for a bare in-clone run that never linked, the
one case where it is correct.
