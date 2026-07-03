# System lens — CMS repo

Inventory and assessment of this repo's machinery. Snapshot: 2026-07-02.

**Reader caution recorded at audit time:** the mapping agent's assessments largely
mirror the repo's own self-description (docs written by the same system that maintains
them). The inventory facts below were grep-/test-verified; the judgment calls were
re-weighed against the independent Monition and global-config lenses in
[synthesis.md](synthesis.md) — which is where the less rosy verdicts live.

## tools/ — 11 production scripts + 5 test suites (all passing)

| Script | Lines | Purpose | Trigger | Status |
|--------|------:|---------|---------|--------|
| autoflag.py | 184 | Tier-2 flag backstop: regex floor + self-improving lexical corpus | Stop hook | live; has `stop_hook_active` guard, never blocks |
| session_tokens.py | 388 | Sums API usage across session + subagent transcripts into session log | SessionEnd hook | live, tested (356-line suite) |
| craft_reminder.py | 96 | Once-per-session pointer before edits to governed material; merges fork-local overlay | PreToolUse (Write\|Edit) | live, tested |
| cms_lint.py | 305 | Pre-commit linter: ERROR relative-links/placeholders; WARN provenance/decision-status | git pre-commit | live, self-governing |
| extract_session.py | 359 | Lifts role-labelled text from session JSONL; `--canary` mode detects harness schema drift | manual via /wrap-session | live |
| flag_corpus.py | 240 | Lexical scoring vs corpus; read-only on hook path, mutates only at mine-time | mine-session step 0d | live, tested |
| deploy_settings.py | 193 | JSON surgery for bootstrap (MCP approval, hook wiring) | /deploy | live, tested |
| lint_skeleton.py | 298 | Vendored managed copy of shared checks; mirror-parity with cms_lint | imported by fork-local lint.py | live; drift-guarded |
| backfill_decision_status.py | 262 | Assisted-confirmation backfill of decision `status:` frontmatter | manual (migration) | support tool |
| migrate_lint.py | 138 | Detects pre-seam lint.py; flags for manual migration, never auto-overwrites | `--update` validation | support tool |
| craft_reminder_local.py | 22 | Fork-local RULES overlay; never managed, survives `--update` | imported | fork-local template |

No dead or unwired scripts found. `test_lint_mirror.py` guards cms_lint ↔ lint_skeleton
parity on every commit.

## .claude/skills/ — 16 skills, no dead ones

codify, dispatch, deploy, eos, flag, mine-session, wrap-session, housekeep (286 lines,
seven transient-store classes), postmortem, concern-review, handoff, scrutinize,
grill-me, confer (214 lines + feedback.md), update-roadmap, diagnose-process.

Apparent overlaps are deliberate splits: flag→codify (capture vs route),
handoff vs wrap-session (decision-ready resume vs retrieval archive), postmortem vs
concern-review (incident response vs pre-action gate). `/scrutinize` absorbed the old
architecture-width-scan (2026-06-28). Three skills carry feedback.md files (handoff,
grill-me, confer) — active gotcha capture. Skills have no test suites (declarative; but
see synthesis Gap 5 — behavioral evals are the missing layer, and that gap is real).

## method/ — 11 docs, every one trigger-stated and referenced

deploy (131), dispatch (200), tooling (105), lesson-routing (86), takeaway-store (152),
learning-loop (49), summaries (93), read-path (87), write-path (83), architecture-doc
(175), tech-debt (33). No orphans; reference counts range 3–37.

## starter/ + landing/ — day-one fork surface

Five starter templates (~486 lines): CLAUDE.md, architecture, debt, road, plus the
workstream/bucket generator prompt. Landing zone resolves `$CMS_LANDING_ZONE` first,
in-repo `landing/` as zero-config fallback. First-run path: fork → `/deploy` or
`bootstrap.sh` → Monition install/join, hook wiring, template instantiation, doctor
check. Zero-config is genuine.

## docs/ — DESIGN, debt, road, decisions

- **DESIGN.md (live verdicts, 2026-06-20):** four seams — hot↔cold context, closed
  learning loop, artifact traceability, and the *open* edge: no value model on firing
  (everything fires on bare trigger match; EV-scored engine is Monition-owned future
  work gated on accumulated honest ratings). Forward roadmap all evidence-gated:
  retrieval routing, tier-3 eval discipline, firing engine, warm backlog rating,
  store-backup hygiene.
- **debt.md:** 5 items resolved by the 2026-07-02 audit pass; 2 awaiting decision —
  the `cms update` vs `monition sync` collision (both own `mine-session/SKILL.md`;
  producer undecided) and monition store.py int-cast hardening; 1 watch item (resident
  daemons); 1 declined-on-record (meta-freeze).
- **road.md:** Phase 1 (audit remediation, 5 buckets) complete 2026-07-02; Phase 2
  unsketched, candidates gated in DESIGN.md.
- **decisions/:** 25 docs (2026-06-13 → 2026-07-02), all with linted
  `status: decided|superseded` frontmatter; supersession chains resolve. Themes: fleet
  propagation (6), firing discipline (6), skill/workflow design (5), store/routing (4),
  deploy/bootstrap (4).

## Hooks wiring (.claude/settings.json)

PreToolUse(Write|Edit)→craft_reminder; Stop→autoflag; SessionEnd→session_tokens;
SessionStart→`monition session-brief`; UserPromptSubmit→`monition prompt-hook`. All
fail-open. Conditional wiring (2026-06-28 decision): with the global anchor present,
per-repo wiring is craft_reminder only; standalone forks wire all three.

## Propagation contract

Managed set of six vendored files; SHA256 version stamp in `tools/.cms-version`; fork
linter WARNs on stale stamp when the canonical source is reachable, silent otherwise
(fail-open). Fork-local seams (`lint.py` wrapper, `craft_reminder_local.py`) are never
touched by `--update`. Zero-dependency (stdlib only) by constraint.

## Honest gaps (as found by this lens; ranked in synthesis)

- **No behavioral eval loop** on skill/method-doc quality — validation is author
  judgment + consent gate; underperforming skills fail silently until noticed.
- **No canary/dark-launch for managed-tool updates** — `--update` re-vendors wholesale;
  a bad lint_skeleton change hits all forks at once (mitigated by stdlib-only, small
  surface, mirror test — risk low but nonzero).
- **No scheduled deprecation review** — retirement of method docs/skills/decisions
  relies on manual audits.
- **No end-to-end hook-ordering tests** (unit tests only; fail-open design bounds the
  damage) and **no multi-fork update scenarios** in tests (manual dogfooding).

## Lessons the mapper flagged as worth keeping

- Mirror-parity tests are small but load-bearing for any vendored copy.
- Fail-open + once-per-session keying beats tuning knobs for hook noise.
- Schema canaries (`extract_session.py --canary`) catch external-contract drift before
  silent data loss.
- Frontmatter as machine-checkable intent (`status:` linting) beats hand-maintained
  deprecation registries.
- Two propagation mechanisms owning one file (`cms update` vs `monition sync` on
  mine-session/SKILL.md) is fragile — decide the producer before shipping.
