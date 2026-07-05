---
name: deploy-check
description: After a change is implemented in a CMS-machinery repo, verify it is correct per CMS standards AND fully propagated across every surface it touched — symlinks, bootstrap/fork distribution, dotfiles channel, hook wiring, governing method doc, decision record, mirror-back, lint. Use when the user invokes /deploy-check, says "make sure this is deployed right / propagated / done per CMS standards", or right after editing a skill, tool, starter template, hook, or method doc. NOT a runtime behavior check (that's /verify), NOT wiring CMS into a repo (that's /deploy), NOT a bug/quality pass (that's /code-review).
---

# deploy-check

You are verifying that a change already implemented in this repo is **correct per CMS
standards** and **fully propagated across every surface it touched**. A change can be
functionally right and still be half-deployed: a new skill with no global symlink, a
managed tool whose fork-local config got clobbered, a hook stripped from the committed
settings, a contract change with no decision record, a fork-teaching edit that never
reached the mirror-back queue. This pass catches that gap.

**Anti-goal:** not a re-lint, not a behavioral test, not a repo-wide audit. It is scoped
to *the change just made* — classify which surfaces it touched, check only those, and
report per-surface. It proposes fixes and (with the ✗ items) hands you the exact command;
it does not silently mutate the repo beyond creating a missing skill symlink when asked.

## Gotchas

- **A skill you added THIS session has no global symlink yet — it exists in the repo but
  is not discoverable globally.** `--link-global` symlinks each skill dir *at bootstrap
  time*; a dir created later is invisible until linked. Tell: you wrote a new
  `.claude/skills/<name>/` → `readlink ~/.claude/skills/<name>` will be empty → link it
  (`ln -s "$PWD/.claude/skills/<name>" ~/.claude/skills/<name>`) before calling it done.
- **"It's symlinked so the edit is live" is only true if the DIRECTORY is the symlink —
  never infer it from a file `ls`.** `ls -la ~/.claude/skills/<name>/SKILL.md` resolves
  *through* the parent symlink and prints a plain `-rw-` file, which reads as "not
  linked." Check with `readlink ~/.claude/skills/<name>` (the dir), not a stat of the
  file inside it.
- **A managed tool re-vendored by `bootstrap --update` silently clobbers fork-local
  config carried in its own body** (a POINTER/RULES/config block). Logic is unchanged, so
  the diff looks innocuous. Tell: the change touched a `tools/` file that also holds
  per-project config → verify the fork-local block survived, don't trust the clean diff.
- **Removing a hook from the committed `.claude/settings.json` to "globalize" it silently
  strips it from every forker.** `bootstrap.sh` does not wire hooks — that committed file
  IS the only hook wiring an in-place forker inherits. Globalizing = ADD to the global
  `~/.claude` dotfile and KEEP the committed copy; never move it out.
- **A personal-config edit (`~/.claude`, `~/dotfiles`) must NOT go through
  `upstream-candidates.md`.** That queue is the fork-distribution channel for
  teaching-surface changes only. The personal-config channel is separate — route dotfiles
  work to `~/dotfiles`, not the mirror-back queue.

## Protocol

### 0. Scope to the repo, fail open

Detect which CMS surfaces this repo even has: `.claude/skills/`, `method/`, `starter/`,
`tools/cms_lint.py`, `bootstrap.sh`, `.claude/settings.json`. If none are present, this is
not a CMS-machinery repo — say so in one line and stop. Every probe below is independent:
a missing directory, a non-git cwd, or a tool that errors → skip that surface silently and
continue. Never abort the whole run on one failed probe.

### 1. Identify the change and classify surfaces

List what changed — working tree *and* the most recent commit if the change was just
committed (`git status --short`; `git diff --stat HEAD~1` when relevant). Map each touched
path to a surface:

| Path pattern | Surface |
|---|---|
| `.claude/skills/<name>/` | shared skill |
| `tools/*` | managed / fork-local tool |
| `starter/*` | per-project template |
| `method/*.md` | teaching-surface doc |
| `.claude/settings.json` (hooks block) | hook wiring |
| `~/.claude/*`, `~/dotfiles/*` | personal-config channel |
| `docs/decisions/*`, a contract/design change | decision record |

Run only the checks whose surface was touched.

### 2. Per-surface checks

**Shared skill**
- *Symlink liveness.* `readlink ~/.claude/skills/<name>` must resolve to
  `<this-repo>/.claude/skills/<name>`. If empty → the skill is not globally linked (new
  skill, or link never run): fix = `ln -s "$PWD/.claude/skills/<name>"
  ~/.claude/skills/<name>` (or `./bootstrap.sh --link-global`, which is idempotent). If it
  resolves, `diff` the global-resolved `SKILL.md` against the repo file — identical means
  the edit is already live with **no bootstrap needed**; a mismatch means the symlink
  points elsewhere (stale copy) — investigate before trusting it.
- *Governed by method.* Identify the `method/` doc that governs the skill's behavior
  (`grep -rl` the concept). Read it and verify the edit is consistent **structurally**
  (does the changed rule match the contract's actual mechanism), not nominally (a matching
  name is not evidence).
- *Three-layer self-containment.* `## Gotchas` present when a firing lesson has been
  earned (never a duplicate of a body rule); feedback provenance in the skill's own
  `feedback.md`; **no dependency on another skill's or an external repo's files** — such a
  reference dangles when the skill is symlinked or shipped to a fork.
- *Fork distribution.* Skills reach forks via `bootstrap.sh` `cp -R` on `--update` — so
  the change flows to forks only once committed; note if it is still uncommitted.

**Tool (`tools/`)**
- If the tool is hook-wired, its wiring must be in the committed `.claude/settings.json`
  (the only wiring a forker inherits) — confirm it was kept, not moved out.
- If the tool carries fork-local config in its body (POINTER/RULES/config block) and the
  change re-vendored it, verify that block survived the overwrite.

**Starter template (`starter/`)**
- `{{PLACEHOLDERS}}` intact (no accidental resolution to a concrete value). Read the
  governing `method/` doc before trusting a template edit.

**method/ doc**
- Run `tools/cms_lint.py <file>` — it WARNs on provenance / external-reader leaks. The
  teaching surface must read for an external reader from line one.

**Hook (`.claude/settings.json`)**
- Committed copy kept (never stripped to globalize). If globalized, the global `~/.claude`
  dotfile has an ADDED copy, the committed one is unchanged.

**Personal-config channel**
- Confirm the edit landed in `~/dotfiles` / `~/.claude` and did **not** get queued to
  `handoffs/upstream-candidates.md` — wrong channel.

**Decision record**
- If the change altered a design call or a contract (coverage, semantics, an interface):
  a dated `docs/decisions/` file exists with `status:` frontmatter, and nothing prior it
  supersedes is left unmarked.

**Mirror-back**
- If this edit was made in a **downstream fork** and is a teaching-surface change
  (`method/`, skills, `starter/`, linter), it belongs in the shared upstream-candidates
  queue — the landing-zone hub when set, else the fork's own `handoffs/upstream-candidates.md`
  (the canonical location in CLAUDE.md's mirror-back rule). In the CMS upstream itself →
  N/A. A trigger-shaped
  *lesson* never queues here — it goes straight to the shared Monition hub (`reach:
  general`) and is already live everywhere.

**Lint**
- `tools/cms_lint.py <changed files>` clean — ERROR blocks, WARN advises.

### 3. Report

One line per touched surface: `✓` (correct + propagated), `✗` (with the exact fix
command), or `N-A` (surface not touched — omit unless its absence is worth noting). If
every touched surface is `✓`, say so in a short confirmation rather than a full table.
