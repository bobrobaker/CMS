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

- [ ] **Feedback↔monition graduation seam (design, open).** How a skill-feedback
  entry graduates into a monition row is unresolved — the parked synthesis wrongly
  treated all monition triggers as probabilistic (`session_start`/`edit_path` are
  deterministic; only `on_demand` is fuzzy). Interim call in effect: keep the
  three-layer text feedback system. Pick up from
  `docs/decisions/2026-06-17-skill-three-layer-and-feedback.md` (caveat noted there).
  (Routed from handoffs/deferred-actions.md, 2026-08-16.)
- [ ] **Feedback→monition run-marker detection (build, enhancement).** A skill leaves
  an "I ran (+ output)" marker; `/mine-session` detects when the output was adjusted
  and routes the improvement through the codify gate. Detection is the only unbuilt
  piece — the routing exists. Not a blocker.
  (Routed from handoffs/deferred-actions.md, 2026-08-16.)

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
- [x] **cms update vs monition-sync forkgen collision** (found at 2026-07-02 close):
  `update_target`'s `cp -R .claude/skills/.` overwrote monition's generated fork-variant
  `mine-session/SKILL.md` with CMS's upstream variant; `monition sync` then WARNs
  "locally edited — left alone" and `test_generated_matches_cms_regen` stays red even
  after regen (the regen commit 28470e9 is directionally correct; the skill-file fight
  is the remaining cause). Two propagation mechanisms own the same file — decide the
  owner (likely: cms update must skip forkgen-swapped skills, or monition sync must
  re-splice after update). t33's drift class exactly. Also audit the other four forks'
  mine-session for the same clobber.
  **[2026-07-12]** This class fired live: the 2026-07-11 fleet drift (stale `mine-session`
  across forks) is exactly this clobber. Detection now exists (`/housekeep §L`, committed
  a05e43e); the *ownership* decision (cms update skips forkgen-swapped skills, or monition sync
  re-splices after `--update`) ~~is STILL OPEN — §L surfaces the skew but not which variant is
  correct.~~ **[audited 2026-11-03]** decided 2026-07-03 (`docs/decisions/2026-07-03-fork-variant-skills-monition-owned.md`,
  cce33c6): `--update` skips fork-variant skills and runs `monition sync`, which owns them. The "audit the other four forks" ask was discharged by the 2026-07-12 fleet fix.
- [ ] bootstrap.sh:link_global — doesn't exclude fork-variant (`*.fork-overrides.md`-marked)
  skills the way `vendor_skills` does, so a `--link-global` re-run would symlink
  mine-session's raw authoring source (CMS-only step 6, live `forkgen:` markers) into
  `~/.claude` globally. Mirror the vendor_skills exclusion. (Found by deploy-check
  2026-08-23; monition +1'd the fix, no opinion beyond that.)
- [ ] Fractional-factorial eval-helper idea (handoff deleted 2026-07-02, was 16d
  stale with nothing built): a runnable helper measuring how well a CLAUDE.md line
  reduces its target failure, via fractional-factorial design + stats. Three design
  forks were never answered; overlaps DESIGN.md's Tier-3 evaluation discipline
  (gated on labeled-trace volume) — revive there if ever, not as a standalone build.

## Awaiting user discussion

Real, scoped concerns that need a decision from the user before they can be drafted
into a roadmap phase or acted on. Each carries the context that justified surfacing it.

- [x] **Firing-noise plan, remaining steps** (monition) — **closed 2026-07-05**: the
  last remaining step (post-filter re-measurement) ran as monition checkpoint t216
  (row retired). Result: gate stands unsoftened — volume back to the ~350–650/day
  late-June range from the 1,621/day peak, task-notification leak 0, weekly rated
  fraction recovered 7.0% → 17.2% → 24.2%. Note: the 43.6% noise-saved baseline is
  **not comparable post-gate** (the gate changed the decision population; report now
  reads 37.4% by composition, not regression). Full numbers + caveat: monition
  `docs/decisions/2026-07-02-boilerplate-prompt-gate.md` §Update 2026-07-05.
  (History: approved 2026-07-02; gate shipped same day; top-firer-first rating
  already existed (`export-firings --order-by priority`, Phase 7 / d65e9dc); latency
  item done in Phase 8; `SEMANTIC_TOP_K`/threshold revisit owned by Phase 7 B03;
  batch noise-attribution by Phase 7 B04.)
- [ ] **mine-session runs `eval-session` on the authoring session's own transcript**
  (surfaced by monition's t224 re-measure, 2026-07-05). Monition row t169 warns
  exactly against this (the authoring session is a false-FN source — it *discusses*
  the rows it mined, so signature substrings match mentions, not acts), yet the
  mine-session skill's own step invoked `monition eval-session --transcript <own
  session>` (observed live in session e93221a7, fathom, 2026-07-04). Either the
  skill step is wrong (should target *other* sessions' transcripts) or t169 is
  over-strict and should be amended — reconcile, don't leave the skill and the row
  contradicting. CMS owns mine-session; evidence pointer: monition B05
  `Updates` 2026-07-05 (the t169 LOSS entry).
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

- [ ] **mine-session §0c → evidence-contract rater relay** — **approved 2026-11-03, queued as its own build session** (routed from the landing-zone
  handoff "2026-08-26 monition eos-rater-relay-for-cms", 2026-11-03). Monition shipped the
  machinery + relay spec (authority: monition `docs/contracts/evidence-contract-rating.md`
  §Relay, §Host shapes); CMS owns the skill edit, still undone — §0c is the in-context
  LLM pass, no `monition rate --contract`. Shape: export the session's unrated firings →
  fork rater subagent (sonnet; prompt from `rate_protocol.render_rater_prompt`) →
  `rate_protocol.build_batch` plants controls → `monition rate --contract batch.json
  --transcript <path>`; a VOID batch writes nothing and is never retried by editing
  evidence. mine-session is monition-owned (fork-overrides), so verify the regen path
  before editing. Verify the spec against monition@main first — the envelope is 2+ months old.
- [x] **autoflag recall: Item-5 regex subset, threshold, t495 retirement** — **decided 2026-11-03** (`docs/decisions/2026-11-03-autoflag-recall-tuning.md`: Item-5 applied, threshold kept at 0.4, 5 FP entries demerited, t495 retired). (routed from
  the landing-zone handoff "night-report-2026-09-09", 2026-11-03; full report in the
  landing zone's inbox, "2026-09-09 night eval — autoflag backstop recall re-measurement (t495)").
  t495's trigger is met (corpus has helpful>0 entries) and the re-measure ran: recall ≈48%
  upper bound; Item-5 subset +2 genuine / 0 new noise, but both catches come from two
  contaminated meta sessions (b7b8ef0e, c36be3eb). Decisions: (1) apply Item-5 to
  `tools/autoflag.py`? (2) lexical threshold 0.4 → 0.45 (drops 5/6 FPs, costs 2 hits —
  t495 froze threshold moves; arguably liftable now)? (3) demerit FP-producing corpus
  entries, incl. one credited `helpful: 1`? (4) retire t495 (still firing at every
  session start).

- [x] **Tombstone follow-ups** — **closed 2026-11-03** (all three landed, red-teamed on Fable; see the commit). (from `docs/research/2026-11-03-housekeep-revendor-redteam.md`).
  (1) `method/deploy.md` §vendoring describes fork-overrides and manifest retirement but
  not `.fork-retired` tombstones. That's a teaching-surface edit, so it goes through the
  proposal gate. (2) deploy-check's vendored-currency probe reports a tombstoned skill,
  and a repo with no commits (cardstate), as UNVERSIONED with a gitignore explanation,
  which is the wrong diagnosis in both cases. Teach it to recognize those states.
  (3) `--update` runs `monition sync` with its output discarded while sync rewrites
  committed `settings.json`/`.mcp.json`. Consider surfacing its warnings instead.

- [ ] **P3 must consume the `export-firings` contract** (routed 2026-11-03 from the
  upstream-candidates queue; past its own 2026-11-01 expiry with P3 unstarted). When the
  tier-3 (P3) harness is built: cite monition `docs/contracts/export-firings.md` (v1)
  instead of duplicating it; confirm its field list matches what P3 consumes (additive
  columns need no version bump); and decide whether `trigger_kind=resurrection` firings
  — synthetic helpful-equivalents injected by the suppression-resurrection gate — count
  toward helpful-rate or get excluded (they're identifiable client-side; tell monition if
  you want an `--exclude-synthetic` flag). `trigger_kind` is free-form, not a closed enum.

- [ ] **Contract docs into the architecture-freshness check** (doc audit 2026-11-03). The
  propagation contract kept documenting a removed symbol (`_stamp_of`) for months.
  `check_architecture_freshness` already resolves `path` / `path:symbol` spans for docs with
  `doctype: architecture`; add that frontmatter to `docs/contracts/*.md` (opt-in) and the
  existing WARN covers them. Bare-symbol resolution stays the audit's job.
- [ ] **Housekeep probe: checkpoint rows still active long after `not_before`** (doc audit
  2026-11-03). monition t554 (due 09-27) and t618 (wake 10-05) fired at session start and were
  ignored for a month, so two Phase-7 gates went unjudged. A §G store probe —
  `status='active' AND trigger_kind='session_start' AND not_before < today-14` — reports "woke
  N days ago, still active". It needs the store, so it's a housekeep probe, not a commit lint.

## Watching (no action needed, just context)

- **road↔DESIGN phase-status mismatch** (doc audit 2026-11-03): a road.md phase marked active
  while DESIGN.md lists it Landed happened once (Phase 2). Worth a lint only once CMS has more
  than two phases; forks have no DESIGN.md, so it's CMS-only.
- [ ] **Scope-creep watch — monition daemons.** `MONITION_SQL_SERVER` +
  `MONITION_EMBED_DAEMON` together mean two resident daemons are now recommended for
  what began as a one-line reminder injector. Documented and opt-in — just watch it,
  no action implied.

## Declined (recorded so it isn't re-proposed)

- A runway-scoped meta-freeze was recommended by the 2026-07-02 audit. The user
  refused: a deliberate choice to continue meta work post-fathom-release before
  returning to portfolio projects. Do not re-raise this without new information.
