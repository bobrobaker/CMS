# System lens — Monition (takeaway store + firing engine)

Sources: the Monition code repo and the cross-repo hub store at
`$CMS_LANDING_ZONE/monition`, with live SQL queries. Snapshot: 2026-07-02.

## Architecture

**Storage:** Dolt (version-controlled SQL) hub store; schema v8. Tables:
`takeaways` (221 rows), `firings` (6,312), `decisions` (12,716 fire/suppress decisions
with EV reasoning), `violations` (16 false-negative events from signature-based
detection), `mutations` (6 lifecycle mutations).

**Matching cascade** (`on_demand_match` in `store_write.py`):
1. Lexical pass — prefix/keyword match (user-authored deterministic triggers).
2. Semantic pass — embedding ranking via the learned L2' head path (paused; see below).
3. Per-row `sem_threshold` (v8) for row-specific sensitivity.
4. Per-session dedup — no re-fire of rows already disclosed this session.
5. Injection cap — lexical hits always kept; semantic hits capped at `SEMANTIC_TOP_K=5`,
   then lowest-scoring dropped past `INJECTION_CHAR_BUDGET=6000` chars.

**Trigger kinds** (203 active rows): `on_demand` 179 (88%), `edit_path` 21,
`session_start` 2, `tool_call` 2.

**Runtime:** no resident daemon required — cold subprocess model, with optional
`dolt sql-server` + pymysql wire client (Phase 8, 2026-07-02, ~0.9ms latency) and
optional embed daemon for warm embeddings. Fail-open throughout: absent
store/daemon/server degrade to the subprocess CLI path. `match_gotchas` MCP tool
exposes pull-based retrieval (not the backbone).

## The critical numbers

| Metric | Count | Read |
|--------|-------|------|
| Total takeaways | 221 | — |
| Active | 203 | 18 retired (8%) |
| General-reach | 145 | fire everywhere; 59 project-scoped |
| Never fired | 18 | 8.9% of active rows are dead wood |
| Total firings | 6,312 | — |
| Rated | 674 | **10.7% rating rate** |
| Helpful | 319 | 47.3% of rated |
| Noise | 355 | **52.7% of rated — noise wins** |
| Unrated | 5,638 | 89.3% of all firings |
| Rows with zero feedback ever | 45 | — |
| Rows with ≥1 unrated firing | 198 | 97.5% of active rows |
| Violations (false negatives) | 16 | Phase 6 recall signal |

**Rating rate by trigger kind** — the shape of the eval problem:

| Kind | Fires | Rated | % rated |
|------|-------|-------|---------|
| on_demand | 6,086 | 594 | **9.8%** (dominant kind, worst-rated) |
| edit_path | 102 | 52 | 51% |
| session_start | 101 | 7 | 6.9% |
| recurrence | 18 | 18 | 100% (manual) |
| tool_call | 3 | 1 | 33% |
| resurrection | 2 | 2 | 100% (manual) |

**Top-firing rows are unmeasured:** t117 — 269 fires, 7 rated (2.6%); t85 — 257 fires,
6 rated (2.3%); t102 — 173 fires, 3 rated (1.7%). The EV scorer has no ground truth for
these rows; it operates blind on cold-start or stale ratings.

**Injection-cap suppression (over-firing evidence):** 123 capping events in the hook
error log; 5,393 semantic hits suppressed in total; mean 43.8 per event; max single
suppression 101 hits. The matcher returns 40–100 semantic candidates per prompt; the
cap is a band-aid on a selectivity problem.

## Relevance head — honest NO-GO

- Learned logistic regression over L2-normalized prompt⊕row embedding product
  (`src/monition/relevance/head.py`). **Status: PAUSED** — failed the B02 gate
  (2026-06-21).
- Leakage-corrected honest LORO CV AUC: 0.669 (n=46 rows); 95% CI lower bound
  0.551–0.778 across variants; pre-registered usefulness threshold 0.60 on the CI lower
  bound; best CI-LB 0.582 < 0.60 → NO-GO. The spike's original "0.78 grouped-CV AUC"
  headline flipped to 0.67 under leave-row-out red-teaming.
- Operational read: would suppress only ~20% of noise at ≥90% helpful retention.
- Phase 5 re-opened 2026-07-02 on independent grounds: the rated corpus grew 129→594
  on_demand firings / 137 rows; B06 re-tests both buried premises (metamatch, head)
  under honest LORO CV.

## Boilerplate gate (2026-07-02)

- Deterministic prefix filter in `prompt_hook()` (`hooks.py` ~line 382):
  `_BOILERPLATE_PREFIXES = ("<task-notification>",)` — skips harness-generated prompts
  before matching. Prefix (not contains) so human prompts mentioning the tag mid-text
  still match.
- Measured impact: 7 skips logged since the gate; 837 of 5,878 historical on_demand
  firings had the boilerplate prefix. Post-decision audit of the gated class: 756
  unrated, 57 noise, 24 helpful (~3% helpful rate) — the gate has measurable collateral
  and stands; most gated rows re-fire on real prompts anyway.
- Rationale: batch mis-ratings (rows co-fired with task notifications rated noise
  wholesale) + injection-cap saturation. The decision doc explicitly rejects a generic
  "looks systemy" heuristic; new prefixes must show repeated evidence in
  `firings.situation`.

## EV scoring and the Filter-not-Gate stance

- `ev_score = helpful / evidence_count`, threshold 0.5, cold-start always-fire until
  ~N=3 evidence per row. 6,204 cold-start fire decisions vs 6,512 suppress decisions.
- **Context-blind:** a row noisy in context Y gets suppressed globally, losing helpful
  firings in context X. The 2026-06-18 Filter-not-Gate decision says noise ratings
  should tighten `trigger_spec` (the Filter), with the Gate as last resort — but in
  practice rows have not mutated to narrower triggers, so the Gate carries the noise
  burden.

## Lifecycle

- **Creation:** `/mine-session` (routing via lesson-routing v5), `/codify`, `/flag`,
  `/adopt <file>` (tier-0 graduation).
- **Dedup at birth:** `find_resurrection()` blocks re-learning suppressed near-matches;
  `find_active_duplicate()` blocks near-duplicate births; consent gate forces an
  explicit `--resolve log-helpful:tN | merge:tN | new`.
- **Mutation:** Phase 7 machinery exists (proposals, `migrate_kind`, `retarget`) but
  only 6 mutations total = **2.7% mutation rate** — rows fire or die, they don't
  improve. The Phase 7 exit gate ("equal-or-better helpful rate post-mutation") is
  stated but has no automated check.
- **Retirement:** manual only (`status='retired'`, 18 rows). **No decay/consolidation
  mechanism** — no age-, staleness-, or performance-based retirement; steady-state
  corpus growth is unbounded.

## Tests, docs

41 test files (store contract, injection cap, boilerplate gate, embeddings, metrics,
hook integration, decisions, MCP server, replay/eval). 17 decision docs; road.md phases
1–8 (5 and 8 active); contracts for the store schema and the (paused)
relevance-cascade. Noted concerns: relevance-cascade.md describes the unproven paused
head and may need an archival note; the Phase 7 exit-gate check is manual.

## Failure modes, ranked

- **CRITICAL — unrated firings unbounded:** 5,638 unrated and growing faster than any
  manual rating pass; the eval loop is effectively fictional for `on_demand` rows.
- **CRITICAL — over-firing on on_demand:** 96.4% of volume, 9.8% rated, 40–100
  candidates per prompt suppressed by cap.
- **MODERATE — relevance head failed its gate** (honest NO-GO; re-test dispatched).
- **MODERATE — boilerplate gate collateral** (~3% helpful in gated class; measured and
  accepted).
- **MODERATE — rating backlog undrainable at current pace** (a 50-firing session yields
  ~5 ratings; the queue never drains).
- **MODERATE — rows not mutating** (2.7%; Filter-not-Gate unrealized in practice).
- **LOW — reach-filter leakage risk** (145/203 rows general-reach; routing-discipline
  dependent, no observed abuse).
- **LOW — no decay/consolidation** (see synthesis Gap 3).
- **ARCHITECTURAL — no unified failure taxonomy:** crashes, cap events, skips,
  decisions, and firings live in separate logs/tables; "why did this fail" requires a
  multi-table join; no single view.

## Unresolved questions

1. When does the on_demand rating rate become sustainable? (Depends on evidence-gated
   mine-session adoption; 9.8% cannot feed EV learning.)
2. Will the Phase 5 B06 re-test pass on the grown corpus (594 rated / 137 rows)?
3. Why is the mutation rate 2.7% — are proposals not generated, or generated and
   rejected?
4. Should the boilerplate gate expand? (Decision doc: only with repeated evidence per
   prefix; no generic heuristic.)

## Files to watch

- Hub store: `$CMS_LANDING_ZONE/monition` (dump.sql checkpoint)
- `src/monition/hooks.py` (~382) — boilerplate gate
- `src/monition/score.py` — EV scorer (context-blind risk)
- `docs/decisions/2026-06-21-relevance-cascade-b02-no-go.md` — pause & re-open record
- `docs/road.md` — phases 5–8 status
- `method/lesson-routing.md` (v5) — row-creation routing discipline
