# 2026-06-17 · CMS is a forkable reference implementation, not a generator

> **Refined in part (2026-06-18, see [`2026-06-18-session-archive-tooling-global-anchor.md`](2026-06-18-session-archive-tooling-global-anchor.md)):**
> this decision single-sourced shared machinery and symlinked the skills, but left the
> session-archive *tooling* on the old copy-per-project path. The follow-up applies the
> same single-source rule to that tooling via a `~/.claude/cms` dotfile anchor. The
> forkable model itself is unchanged.

**Decision.** Discard the generator model. CMS no longer interviews you and *copies*
machinery into a fresh `~/projects/<name>` (`/instantiate`). It is a **forkable
reference implementation** of the context-management system: you fork or clone it, run
`bootstrap.sh`, and the machinery is live in that repo. Shared machinery is
single-sourced in the repo (`.claude/skills/`, `tools/`), not templated per project.
Monition ships as a **declared dependency** installed by bootstrap (the store defaults
to SQLite; Dolt is optional) — there is no tier-0 floor and no `monition init --adopt`
graduation. Cross-project context resolves through a **configurable landing zone**
(`$CMS_LANDING_ZONE`, else the in-repo `landing/` fallback), so a fresh fork runs with
zero setup. Governance changes route through an extended `/codify` that classifies
personal-vs-system-vs-project and deploys to the right layer.

**Why.** The generator carried two costs that outweighed it:
- **Drift tax.** Copying "generic" machinery into N projects desyncs each copy from a
  single source of truth — the opposite of what generic machinery is for.
  Single-sourcing (and, for the author, symlinks) makes one canonical copy that is
  instantly live everywhere and ships unchanged to forkers.
- **Unfold complexity.** The two-tier takeaway path — a frozen stdlib `lessons_fire.py`
  + flat `lessons.md` at tier-0, graduating one-way to a live Monition store — wasn't
  worth its machinery. A module shipping with a dependency is normal; the dependency is
  cheaper than the unfold.

**Supersedes.**
- `2026-06-14-instantiate-store-flag.md` — **fully.** `/instantiate`, tier-0, and the
  `--store` flag are gone. What carries forward is that decision's finding: firing
  provenance (`git_sha`/`session_id`/`situation`) is capture-time-only and impossible
  to backfill, so the store is worth standing up from session one. The argument that
  justified an *opt-in* flag now justifies the store being the **only** path.
- `2026-06-14-cms-owns-host-instantiation.md` — **in its instantiation framing.** CMS
  no longer "orchestrates deployment" via `/instantiate`; deployment is fork +
  bootstrap. The underlying boundary survives intact: **Monition owns the machinery**
  (store contract, `init`/`sync`/`migrate`), **CMS owns the discipline** (method,
  skills, the installer, lesson-routing). `bootstrap.sh` is CMS's deploy surface,
  replacing the generator.

**Locked this session (detail in the refactor plan + per-workstream commits).**
- Single-source machinery; the author's `~/.claude` consumes it via opt-in symlinks
  (`bootstrap.sh --link-global`, backup-first), never copies.
- Landing-zone contract: env var → in-repo fallback; never a committed symlink; any
  personal store mapping stays out of this repo.
- SQLite is the default store backend, Dolt optional behind a seam (see monition
  `docs/decisions/2026-06-17-storage-backend-sqlite-default.md`).
- Publish at the end, on the de-provenanced state: CMS public, monition public.

**Anti-goal.** CMS is not a framework you depend on as an opaque package, and not a
cookie-cutter that scaffolds a project then disconnects. It is a reference
implementation you fork and *own*: bootstrap wires it live, and `apply-to-target` can
copy the machinery into an existing repo (accepting the drift cost a copy implies).
