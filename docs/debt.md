# CMS — tech-debt shelf

Project-local deferred work: refactors, architecture concerns, "fix later" items
spotted while editing. One row per item, append-only; check off when done, delete when
it stops mattering. Not the roadmap (planned work, `docs/road.md`) or `docs/decisions/`
(calls made) — this is debt discovered mid-implementation, plus (below) broader
deferred/awaiting-decision items carried over from the 2026-07-02 system audit that
don't yet have an owner or a decision.

**Capture trigger:** after a logical chunk, make one pass over the functions you just
edited and append anything deferred here, with enough locus to act on it cold.

**Row format:** `- [ ] path:symbol — observation (why deferred)`

## Shelf

- [x] (Done 2026-07-02: homed in dotfiles, symlink repointed.) `~/.claude/skills/agents-view` — the skill is a loose, untracked directory (no git
  home); it survives only until the next reimage. Needs a repo to live in.
- [x] (Done 2026-07-02: surgical-commits was already owned by /eos step 3; replay-fidelity
  migrated to hub row t215; deferred-work superseded by monition road.md. Index carries
  the disposition note.) `~/.claude/projects/-home-bolun-projects-monition/memory/MEMORY.md` — 3 entries
  violate the context-over-auto-memory policy (durable knowledge belongs in that
  project's own takeaway store / decisions, not harness auto-memory). Migrate-or-delete;
  brain2 already got this treatment on 2026-06-18.
- [x] (Done 2026-07-02: housekeep probe J added, ages by first-record timestamp — mtime proved unreliable; 0 prunable today, actionable ~August.) `~/.claude/projects/` retention — 769MB across 1,110 transcript dirs, unbounded
  growth. Candidate for an age-based prune housekeep probe.
- [x] Global permissions (`~/.claude/settings.json`) — confirmed intentional by the
  user 2026-07-02; reviewed, no change. (Original concern:) allow-list grants `Bash(python*)`
  everywhere plus `skipDangerousModePermissionPrompt: true`. Confirm this breadth is
  still intended, not a leftover from earlier convenience tuning.
- [x] `ai-workflow-lab` (repo) — retired 2026-07-02: README banner added; Workboard's
  VVsim entry also corrected to dormant-since-2026-06-14. (Original:) retirement
  approved (dead 62 days). Concrete action
  still TBD: a workboard note or archive, explicitly no deletion.
- [x] (Done 2026-07-02: 17 descriptions trimmed, −1,980 chars / 21.7%; five left as already-tight.) `.claude/skills/*/SKILL.md` — 24 skill descriptions run 250–754 chars each and are
  loaded into every session in every project. Trim-pass candidate once a session can
  spare the read-budget attention.
- [x] (Done 2026-07-02: three headings added; routing-vN contract line untouched.) `method/lesson-routing.md` — has zero `## ` headings, which defeats the
  mandated `grep -n "^##"` structure-scan convention (CLAUDE.md's read-budget rule).
  Needs headings added.
- [x] `dolt` 2.1.6 → 2.1.10 — done 2026-07-02 (binary swapped, hub sql-server restarted on 2.1.10, monition verified).
- [x] `~/.claude/tool_logger.py` hook ↔ `VVsim/.claude/commands/diagnose-mistake.md` —
  retired as a pair 2026-07-02 (user call): the command routed fixes to pre-CMS
  vocabulary (`introspect_notes.md`, `.claude/rules/`) and was used once ever;
  `/postmortem` + transcripts supersede it. Hook unwired from global settings; script
  kept in dotfiles for a one-line rewire; `~/.claude/tool_trace.jsonl`(+`.1`, ~10MB)
  left on disk, safe to delete.
- [ ] monition `store.py` readers — `id`/`takeaway_id`/`evidence_count` aren't cast to
  `int`, so they arrive as strings through the Dolt-server transport (same shape as the
  fixed `cold_start` bug, and technically violates an existing test's
  `isinstance(d.evidence_count, int)` contract). Inert today — nothing does arithmetic
  on them — deferred to a hardening pass rather than bundled with the verified fix.

- [x] Deferred postmortem eval (2026-06-19 SQLite/Dolt postmortem, Step 3) — **ran
  2026-07-02, verdict: effective.** Two-condition cold-judge test: banners alone
  already prevent the false-contradiction failure (stronger than predicted) but leave
  a verify-the-registry residual; road §2's settled line absorbs it — the judge
  affirms the provenance model outright. Recorded as a dated Update on monition's
  `2026-06-18-dolt-default-ours-sqlite-external.md` (whose flip-flop note flagged the
  postmortem). One small follow-on it surfaced: check monition's README/init help for
  any flat "SQLite is the default" lacking the two-audience qualifier.
- [ ] **cms update vs monition-sync forkgen collision** (found at 2026-07-02 close):
  `update_target`'s `cp -R .claude/skills/.` overwrote monition's generated fork-variant
  `mine-session/SKILL.md` with CMS's upstream variant; `monition sync` then WARNs
  "locally edited — left alone" and `test_generated_matches_cms_regen` stays red even
  after regen (the regen commit 28470e9 is directionally correct; the skill-file fight
  is the remaining cause). Two propagation mechanisms own the same file — decide the
  owner (likely: cms update must skip forkgen-swapped skills, or monition sync must
  re-splice after update). t33's drift class exactly. Also audit the other four forks'
  mine-session for the same clobber.
- [ ] Fractional-factorial eval-helper idea (handoff deleted 2026-07-02, was 16d
  stale with nothing built): a runnable helper measuring how well a CLAUDE.md line
  reduces its target failure, via fractional-factorial design + stats. Three design
  forks were never answered; overlaps DESIGN.md's Tier-3 evaluation discipline
  (gated on labeled-trace volume) — revive there if ever, not as a standalone build.

## Awaiting user discussion

Real, scoped concerns that need a decision from the user before they can be drafted
into a roadmap phase or acted on. Each carries the context that justified surfacing it.

- [ ] **Firing-noise plan, remaining steps** (monition). Approved 2026-07-02; the
  boilerplate gate shipped (see monition
  `docs/decisions/2026-07-02-boilerplate-prompt-gate.md`), and top-firer-first rating
  already existed (`export-firings --order-by priority`, Phase 7 / d65e9dc).
  Corrections after reading monition's own road.md (2026-07-02): the latency item is
  **already done** — Phase 8 (hook hot-path) exited 2026-07-02 with warm prompt-hook
  ~431ms / fire-hook ~52ms (the audit's 0.90s was measured pre-B03); struck. The
  `SEMANTIC_TOP_K` / 0.6-threshold revisit is **owned by Phase 7 B03** (per-row
  `sem_threshold`, `tune` as actuator, store v8) — don't propose it as new work; and
  batch noise-attribution (the t91–t98 class) is **Phase 7 B04**. Remaining here:
  only the post-filter re-measurement against the corrected 43.6% baseline.
  Context: firings rose 160 → 1,621/day over 2 weeks; weekly rated fraction fell
  28.8% → 7.5% → 7.0%.
- [x] **Housekeep cadence** — decided 2026-07-02: morning `/housekeep` as the anchor
  habit (concurrency verified safe: auto-reap is limited to two information-preserving
  mechanical classes; everything else proposes). `/housekeep` now stamps
  `$XDG_STATE_HOME/cms/housekeep.last` on completion and `/eos` gained a hygiene
  glance that surfaces staleness ≥2 days. First run still owed — it will catch the
  agents-view stray, monition's auto-memory entries, and the handoff pile.
- [x] **Handoff lifecycle trigger** — decided 2026-07-02: both halves. housekeep probe C
  (already existed) drains the pile on the morning cadence; `/eos`'s hygiene glance now
  closes any handoff this session consumed (delete-or-archive at the moment it's
  cheap). Context that motivated it: only 1 handoff deletion ever in git history;
  8 of 16 root handoffs `status: open`, oldest 16 days.
- [x] **Mirror-back sweep** — resolved 2026-07-02: no "global-patterns" mechanism
  exists; hub rows with `reach: general` absorbed the row-shaped share of mirror-back.
  Charter narrowed in CLAUDE.md (queues = teaching-surface proposals only); fathom's
  queue swept clean (t110 + t170–t174 removed as landed; the 2026-06-16
  naming-overclaim rule landed as hub row t211, reach general, approved 2026-07-02).
  Remaining: monition's ~19-day export-firings doc-citation ask (deferred pending
  labeled-trace volume, per its own note).

## Watching (no action needed, just context)

- [ ] **Scope-creep watch — monition daemons.** `MONITION_SQL_SERVER` +
  `MONITION_EMBED_DAEMON` together mean two resident daemons are now recommended for
  what began as a one-line reminder injector. Documented and opt-in — just watch it,
  no action implied.

## Declined (recorded so it isn't re-proposed)

- A runway-scoped meta-freeze was recommended by the 2026-07-02 audit. The user
  refused: a deliberate choice to continue meta work post-fathom-release before
  returning to portfolio projects. Do not re-raise this without new information.
