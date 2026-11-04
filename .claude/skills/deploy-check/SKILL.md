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
- **A canonical skill edit is not deployed just because the symlink is live — every
  repo that was ever *vendored* still holds a frozen copy.** `bootstrap.sh vendor_skills()`
  copies skill bodies into each bootstrapped repo at vendor time; nothing refreshes them
  until the next `--update`. So after editing a canonical skill there are two populations:
  the symlink (auto-current) and N vendored copies (frozen at their last vendor). Checking
  only the symlink reports "deployed" while every vendored instance ships the old body.
  Note the direction: the vendoring gotcha most people reach for is the *opposite* one
  (a re-vendor clobbering fork-local edits) — that one is about the write, this one is
  about the write that never happened.
- **A re-vendor that was never committed leaves the instance current on disk and stale in
  `HEAD` — and a working-tree diff calls that `✓`.** `--update` writes into the target's
  working tree and stops; committing is a separate, manual, per-repo step that is easy to
  skip when the tree is already dirty with unrelated work. The vendored body a forker or a
  clean clone receives is the one in `HEAD`, so that is what the currency check must diff.
  Tell: the target repo's skill file matches canonical but `git -C <repo> status` has had
  it modified since the last vendor — the drift is real and older than it looks.
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
committed (`git status --short`; `git diff --stat HEAD~1` when relevant — never `diff --stat`
alone: it is blind to untracked files, so newly vendored dirs show only in `status`). Map each touched
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
- *Vendored-instance currency (enumerate, don't spot-check).* A canonical skill change is
  only fully deployed once **every already-vendored copy** of that skill is current. The
  vendor manifest (`tools/.cms-skills-manifest`, written by `vendor_skills()`) makes those
  instances enumerable: any repo carrying one was vendored by this corpus and holds frozen
  bodies. Enumerate them, diff each changed skill against canonical, and list each stale
  instance as its own `✗` with its fix — never sample one repo and generalize.

  **Diff the committed tree, not the working tree.** A vendored file on disk is not what
  the instance ships: `--update` writes into the working tree and stops there, so a prior
  vendor that was never committed leaves the repo looking current on disk while `HEAD` — the
  body a clean clone, a forker, or CI actually gets — is still old. A working-tree diff
  reports `✓` over exactly that state. Compare `git show HEAD:<path>` and treat the on-disk
  body as the secondary signal that separates the two failure modes.

  ```sh
  # Search root: sibling repos by default; override with CMS_FORK_ROOT.
  root="${CMS_FORK_ROOT:-$(dirname "$PWD")}"
  head_body=$(mktemp); trap 'rm -f "$head_body"' EXIT
  for m in $(find "$root" -maxdepth 3 -name .cms-skills-manifest 2>/dev/null | sort); do
    repo=$(dirname "$(dirname "$m")")
    for skill in <the skills changed this session>; do
      rel=".claude/skills/$skill/SKILL.md"
      canon="$PWD/$rel"
      # Committed body is the shipped body. Absent from HEAD => never versioned.
      if ! git -C "$repo" show "HEAD:$rel" > "$head_body" 2>/dev/null; then
        echo "UNVERSIONED $repo $skill"; continue
      fi
      if cmp -s "$head_body" "$canon"; then
        echo "current     $repo $skill"
      elif [ -f "$repo/$rel" ] && cmp -s "$repo/$rel" "$canon"; then
        echo "UNCOMMITTED $repo $skill"   # disk current, HEAD stale
      else
        echo "STALE       $repo $skill"   # both stale
      fi
    done
  done
  ```

  Each state has a **different** fix, so report them separately:
  - `STALE` — never vendored since the change. Fix: `./bootstrap.sh --update <repo>`, then
    commit the CMS-managed paths in that repo. Never hand-edit a vendored body; the next
    vendor overwrites it.
  - `UNCOMMITTED` — a previous vendor ran and was left in the working tree. Re-running
    `--update` changes nothing and reports success; the fix is a **commit** in that repo.
    This is the state a working-tree diff cannot see, and it hides across sessions.
  - `UNVERSIONED` — the path is not in `HEAD` at all, usually because the repo `.gitignore`s
    `.claude/`. Its skills are current on disk but travel with nobody. Do not `git add -f`
    past a deliberate ignore rule — surface it and let the owner decide.

  Two exclusions keep this honest: a **fork-variant** skill (a `*.fork-overrides.md` sibling
  in its canonical dir) is not vendored at all — its currency is monition's regen probe, not
  this diff; and a skill **absent from a repo's manifest** was never shipped there, so its
  absence is a not-yet-vendored signal, not staleness. This check applies in the canonical
  upstream, where the vendoring originates; in a downstream fork there is nothing to
  enumerate. Note the canonical side of the comparison is the working tree on purpose —
  that is what `vendor_skills()` copies — which is why the *Fork distribution* item above
  separately flags a canonical edit that is itself still uncommitted.
- *Read the ✗ count for what it is.* Where the author's machine resolves skills through
  the global symlink farm (`--link-global`), a **global** skill shadows a same-named
  project-local one, so a stale vendored copy is inert *for that author* — the frozen body
  still ships to forkers and to any machine without the farm. So stale instances are a real
  propagation defect worth fixing, but do not report them as "the skill was not running."
  If a behavior genuinely never fired, the cause is elsewhere (an env toggle, a hook) —
  check that before attributing it to staleness.

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
