# Re-vendoring the housekeep fix (8655e9f) to forks: red-team and recommendation

2026-11-03. Trigger: `/deploy-check` on 8655e9f found housekeep STALE in 10 vendored forks
and UNVERSIONED in 2. Inputs: a fresh-context red-team-judge pass over `bootstrap.sh`,
the deploy-check skill, monition `init_sync.py`, and the fleet's state, cross-checked by
the main session (corrections noted inline).

## What `--update` really does (bootstrap.sh)

- **Copies from the CMS working tree, not HEAD** (`update_target` `src=$(git rev-parse
  --show-toplevel)`; `cp` / `cp -R` from `$src`). The running script is also the
  working-tree `bootstrap.sh`. This has already leaked: si-forge HEAD (c3142d0) carries the
  deploy-check line that CMS never committed.
- **Re-vendors every managed skill and tool**, adds skills the fork never had ("vendoring
  NEW skill"), and retires skills CMS stopped shipping (manifest-keyed).
- **Runs `monition sync --root $dst` with its output discarded** (`>/dev/null 2>&1`).
  Sync rewrites committed `.claude/settings.json` (hooks), `.mcp.json`, monition-owned
  skills (mine-session) and docs. Its "skill locally edited — left alone" warnings are
  never seen.
- Writes `CMS_SRC=$src` into each fork's gitignored `settings.local.json`. So running
  from a temporary worktree of HEAD would leave 10 dangling pointers. Don't.
- Never commits. There is no skills-only mode.

## Measured fleet state (this is what a re-vendor actually changes)

| Item | State |
|---|---|
| Skill bodies differing from canonical | only `housekeep` (10 forks) and `deploy-check` (9 forks). deploy-check differs *only* by the uncommitted CMS one-liner. |
| Managed tools | byte-identical to canonical in all forks |
| craft_reminder seam | every fork is post-seam, so no fork config is lost |
| monition `flag` skill | deliberately deleted (monition 021e3c9) but still in its manifest, and no `flag.fork-retired` tombstone. **Any `--update` brings it back.** |
| Uncommitted `mine-session` (8 forks) | from this session's `monition sync` (17:29 today). The red-team called it two-month-old debt; **corrected**. |
| Uncommitted `.claude/settings.json` (Corpus, RCA, Visualizer, boardgame-sim-harness, procap) | real old sync output (mtime 2026-07-31), never committed |
| Visualizer | checked out on `v2-build`, so a commit lands there, not on main |
| cardstate | no commits on master, so UNVERSIONED is not a gitignore case (deploy-check misdiagnoses it) |
| throughput-analyzer | `.claude` gitignored, so it really is UNVERSIONED |
| Shadowing | global skill shadows a same-named vendored one for the author: verified by a sentinel probe 2026-08-26 (decision `2026-08-26-vendored-copies-vs-global-symlink.md`), not re-probed since |

## Verdicts on the three options

1. **Land the pending CMS work, then `--update` each fork, then commit.** Right shape, but
   as written it was unsafe: it said "stash *or* commit" (stash would downgrade si-forge's
   deploy-check), it ignored the monition `flag` comeback, and it left the fork commit
   pathspec undefined. That would sweep three months of sync output into a "housekeep"
   commit and risk RCA's fork-local `tools/lint.py` / `craft_reminder_local.py`.
2. **Hand-copy housekeep only.** Mechanically harmless (`.cms-version` hashes tools only;
   the skills manifest is names only), but it fixes one of three stale surfaces and makes
   hand-copying normal, against the accepted tradeoff.
3. **Defer.** Defensible for housekeep alone: §A's fallback and §J both read author-machine
   paths, and 4 of the forks (Corpus, boardgame-sim-harness, si-forge, uke-tutor) have no
   remote. But it leaves the fork-state debt and the monition comeback unaddressed.

## Recommendation: option 1, corrected

0. **Done in this session (uncommitted):** the §J probe crashed silently (`os.listdir` on a
   missing `~/.claude/logs/sessions` under `2>/dev/null`, the same swallow class 8655e9f
   fixed in §A). Now guarded: with no archive, nothing counts as wrapped, so nothing is
   prunable. Commit it before vendoring so one run carries both fixes.
1. **Commit, don't stash,** the 2026-08-28 tombstone work (`bootstrap.sh`, deploy-check,
   `DESIGN.md`, the decision). The code is sound (`bash -n` clean, `set -e`-safe, keeps the
   manifest truthful). It's behavior-changing machinery that sat in a half-crossed consent
   gate for 2 months, so it needs your explicit yes. Two follow-ups go to `docs/debt.md`:
   `method/deploy.md` doesn't describe tombstones (needs the proposal gate), and the
   deploy-check probe reports a tombstoned skill or a repo with no commits as UNVERSIONED,
   with a gitignore explanation that's wrong in both cases.
2. **Tombstone monition's flag first:** `touch ~/projects/monition/.claude/skills/flag.fork-retired`.
   That's the fork exercising its own authority; it needs step 1's code to be honored.
3. **Per fork:** run `monition sync --root <fork>` visibly (to surface the warnings
   `--update` hides), then `./bootstrap.sh --update <fork>`, then
   `git status --porcelain -- .claude tools .mcp.json`.
4. **Commit per fork in two explicit-path commits, never `add -A`:**
   - A, monition surfaces: `.claude/settings.json .mcp.json .claude/skills/mine-session`
   - B, CMS re-vendor: `git add -u -- .claude/skills tools/.cms-skills-manifest tools/.cms-version`,
     plus any NEW skill dir, plus monition's `flag.fork-retired`
   - Never stage RCA `tools/lint.py` / `tools/craft_reminder_local.py`. For Visualizer,
     decide whether `v2-build` is the right branch. portfolio-site is a live surface: check
     what a push deploys.
5. cardstate and throughput-analyzer: refresh on disk, no commit.

Cheaper fallback if fleet commits aren't worth the time today: steps 0–2 only (land CMS,
tombstone monition), then defer the re-vendor. The stale copies stay inert for the author,
and nothing gets worse.
