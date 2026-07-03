# Synthesis — adversarial comparison vs. industry practice (May–June 2026)

The deliverable of the audit. System inventories: [system-cms.md](system-cms.md),
[system-monition.md](system-monition.md), [system-global-config.md](system-global-config.md),
[system-landing-zone.md](system-landing-zone.md). External evidence:
[industry-memory-context.md](industry-memory-context.md),
[industry-harness-practice.md](industry-harness-practice.md),
[industry-governance-evals.md](industry-governance-evals.md).

## Verdict

The architecture is at or ahead of the published frontier in four places (selective
trigger-matched injection, consent-gated self-modification, pre-registered eval gates,
instruction-file layering). But the system's **central empirical claim — that injected
takeaways are net-positive — is currently unverified by its own instrument**: 89.3% of
firings are never rated, and among the ones that are, noise beats helpful (355 vs 319).
The strongest external finding of the window ("Honest Lying," arXiv:2605.29463) says
exactly this failure mode compounds silently. The gaps that matter are all in the
*measurement and pruning* half of the loop, not the capture half — which is over-built
relative to how starved the eval side is.

## Where the system is at or ahead of the frontier

Each item checked against primary sources, not vibes.

### 1. Selective, rateable injection remains differentiated from first-party memory

Claude Code's first-party auto-memory (default-on since v2.1.59) and subagent persistent
memory load fixed head-of-file blobs per repo/agent; Anthropic **Dreams** (verified real:
platform.claude.com/docs/en/managed-agents/dreams, beta header `dreaming-2026-04-21`) is
offline, non-destructive consolidation. None of them do trigger-matched, per-prompt,
cross-repo, human-rateable injection. The overlap with Monition is in *goal* (durable
cross-session knowledge), not mechanism — collapsing Monition into first-party memory
would lose selectivity, the cross-repo hub, and the rating substrate. This is a
verify-structurally-not-nominally case: surface similarity does not make them the same.

### 2. The governance design matches what the field concluded the hard way

- Formal treatments of consent-gate-style self-modification governance (deontic runtime
  policies, arXiv:2606.19464; layered mutability, arXiv:2604.14717) are **theoretical
  and empirically unvalidated** — the consent gate here has shipped what those papers
  sketch. A personal consent gate is at, not behind, the frontier.
- The Claude Fable 5 hidden-guardrails episode (June 9–12, 2026: silent throttling →
  severe backlash → reversal within ~48h) confirmed the lesson this design already
  encodes: **visible constraint beats silent constraint** — disclosure of governance
  behavior does as much work as the behavior itself.
- OWASP's Agentic Top 10 (2026) now names memory poisoning (ASI06) and recursive goal
  drift (ASI01) as first-class risks; the consent gate + linted decision-status
  lifecycle is a proportionate personal-scale answer to both. Its "Least Agency"
  principle (autonomy earned continuously, never granted and left standing) is a good
  standing frame for auditing whether the gate's scope quietly grows.

### 3. The NO-GO discipline is genuinely rare

The L2' relevance head honestly failing its pre-registered gate — leakage-corrected LORO
CV AUC 0.669, CI lower bound 0.582 < 0.60 threshold set before data was seen → paused,
with a deterministic boilerplate gate shipped instead and its ~3%-helpful collateral
*measured after the fact* — is a documented negative result with a pre-committed
threshold. Contrast: the flagship vendor claim of the window (Anthropic Dreaming's "~6x"
Harvey number) is a press-relayed case study with no methodology, no control, no
reproducibility. Pre-registered gates + post-hoc collateral measurement is stronger
practice than what the labs publish about their own memory features.

### 4. Instruction-file architecture matches official guidance almost exactly

Anthropic's "Steering Claude Code" post (claude.com/blog, June 18, 2026): CLAUDE.md ≤200
lines, procedures → skills, hard guardrails → hooks (CLAUDE.md is *context, not
enforcement*), path-scoped rules over unscoped. The global CLAUDE.md here is 163 lines;
method docs load on stated triggers; hard gates live in the linter/pre-commit; skills
carry procedures. Cross-vendor convergence (Cursor <500-line rules split into
conditionally-loaded files, Copilot ≤2 pages path-scoped, Codex 32KiB nested
closest-wins) all points the same way. One correction to a likely assumption: **Claude
Code still does not natively read AGENTS.md** as of July 2026 (open issues
#11455/#6235) despite widespread blog claims — though AGENTS.md is now governed by the
Linux Foundation's Agentic AI Foundation with Anthropic as a Platinum founder, so an
"import AGENTS.md if present" convention in `starter/CLAUDE.md.template` is a cheap
forward-compatible addition for forks that also use other harnesses.

## Ranked gaps

### Gap 1 — The rating loop can't carry the weight the architecture puts on it (CRITICAL)

The numbers (hub snapshot 2026-07-02, full tables in
[system-monition.md](system-monition.md)): 6,312 firings, 674 rated (10.7%). The
dominant trigger kind, `on_demand`, is 96.4% of volume and 9.8% rated. Top-firing rows
are effectively unmeasured: t117 269 fires / 2.6% rated, t85 257 / 2.3%, t102 173 /
1.7%. 45 rows have zero feedback ever; 198 of 203 active rows carry unrated inventory.
The EV scorer cold-starts most decisions blind, and the backlog grows faster than any
manual pass drains it.

Two sharper points on top of the raw coverage gap:

- **The rated sample reads slightly net-negative**: 52.7% noise vs 47.3% helpful.
  Sampling bias cuts both ways (irritation may over-sample noise ratings), but the
  external research confirms **no published methodology exists for detecting when an
  injection system has gone net-negative** — the rated slice is the only instrument
  anyone has, and it currently points the wrong way.
- **Where rating is cheap, it happens**: `edit_path` fires rarely and is 51% rated;
  manual kinds (recurrence, resurrection) are 100%. The problem is not rating
  discipline but structure — per-firing human rating of a high-volume channel is
  undrainable. This is the sparse-single-rater problem the RLHF literature names and
  nobody has scaled down (confirmed gap; academic benchmarks like EvoMemBench solve a
  corpus-scale, offline version). Don't design as if the labels will come.

**Moves that fit the evidence:**

1. Shift from per-firing to **per-row verdicts via deliberate sampling** — rate a random
   3–5 firings per high-volume row once, rather than aspiring to rate the stream.
2. **Ground more ratings programmatically.** "Honest Lying" (arXiv:2605.29463): 0/121
   open-ended self-reflections identified the correct failure cause; replacing
   self-critique with programmatic failure-signal extraction raised correctness 0%→86%.
   Monition's `violations` table (signature-based false-negative detection, 16 rows) is
   already the seed of this pattern — extend it: a row whose lesson names a mechanically
   checkable condition can be validated by whether the condition recurs, not by a human
   mood at fire time.

### Gap 2 — Over-firing: the injection cap absorbs a matcher problem (HIGH)

123 cap events logged; mean 43.8 semantic candidates suppressed per event; max 101
(visible live in sessions as "+101 more suppressed by cap"). The only circulating
industry heuristic — retrieval quality peaks around 3–5 injected chunks (directional,
single-source) — says `SEMANTIC_TOP_K=5` is right, but a matcher returning 40–100
candidates per prompt means the threshold layer above the cap is not doing its job, and
every prompt pays attention budget for the injected rows plus a suppression banner. The
cap is a symptom, not a solution. The Phase 5 B06 re-test of the head on the grown
corpus (594 rated firings) is already dispatched and is the correct move; if it NO-GOes
again, the honest conclusion is that per-row `sem_threshold` tightening (v8 machinery,
barely used) should be driven by the same sampling-based row verdicts as Gap 1 — not
deferred until a learned head clears its gate.

### Gap 3 — No staleness or decay policy: accretion without pruning (HIGH)

18 of 203 active rows have never fired; mutation rate is 2.7% (6 mutations, ever);
nothing retires a row by age or disuse. Pruning became table-stakes across the industry
this cycle: GitHub Copilot Memory expires facts **28 days unused** and re-validates them
against the current branch; Zep's bi-temporal supersede-don't-delete; Cursor shipped
memory-deletion UI (June 2026); Anthropic ships Dreams only as non-destructive,
human-reviewable output. The important counterweight from the same research pass:
**heavy LLM auto-consolidation currently has more evidence against it than for it** —
two negative ablations (arXiv:2605.18854: no LLM condenser improved quality, 24–94%
token overhead; arXiv:2605.12978: 54% of previously-solved problems failed
post-consolidation) and Mem0's production reversal to ADD-only. So the defensible
pattern for Monition is the conservative one: a **usage-based review queue** — rows
unfired in N sessions, or with noise-majority ratings, surfaced at housekeep/mine time
for consent-gated retirement — never silent auto-merge. `housekeep` sweeps seven
transient-store classes but does not currently do for rows what it does for files;
that's the missing clause.

### Gap 4 — Mined lessons are model self-diagnosis; the consent gate doesn't fully cover that (MEDIUM)

"Honest Lying" is the load-bearing citation: agents storing their own interpretation of
what went wrong were 0-for-121 on correct causes, with full confidence at retrieval.
The pipeline here is better than raw Reflexion — a human approves every row at mine
time, and dedup-at-birth blocks near-duplicates — but the human is approving a
*narrative the model wrote about its own failure*, which is precisely the confabulation
channel. The paper's fix (programmatic signal extraction) maps to a routing preference:
prefer rows whose situation/trigger cite an observable artifact (failing test, lint
error, reverted diff, an actual caught bug) over rows citing the model's theory of its
mistake. Worth one line in `mine-session`'s routing step, not a rebuild.

### Gap 5 — The harness itself has no behavioral eval (MEDIUM; best ROI)

The April 2026 Anthropic postmortem (anthropic.com/engineering/april-23-postmortem) is
the decisive exhibit: three stacked vendor-side regressions degraded Claude Code output
for ~6 weeks; teams running their own workflow evals caught it in ~72 hours; everyone
on vibes took the full six weeks. CMS has structural linting, unit tests on hooks, and
a mirror-parity test — all *structural*. Nothing runs a session against 5–10 canonical
tasks headlessly (`claude --headless --output-format stream-json`), scores outcomes
(LLM judge + rubric written before the run), and diffs a recorded baseline on a
schedule — the top layer of the documented three-layer pyramid (hook tests → skill
evals → workflow evals), run weekly rather than only on change because vendor-side
regressions arrive without a local diff. Two reasons this is the highest-leverage
single build: it is the only gap through which a vendor regression currently reaches
this system undetected, and the operator's stated portfolio thesis leads with designed
evaluations — the governance showcase should carry one for itself.

### Gap 6 — Governance decay under compaction (LOW; mostly covered already)

arXiv:2606.22528 (June 2026) measured compaction silently dropping standing
policy/instruction entries scored low-salience: constraint violations rose 0%→30–59%
across 1,323 episodes; soft policies decayed 8.3× faster than hard safety norms. The
architecture here already has the right counter — Monition rows *re-fire* on trigger
regardless of what compaction dropped, and hard rules live in hooks/linter that don't
ride in context at all. Recorded because it retroactively justifies a design choice:
trigger-based re-injection is one of the few mechanisms that survives this failure
mode — worth remembering when tempted to move a rule from a row into always-on prose.

## Hygiene punch list (global config)

All low-severity; details in [system-global-config.md](system-global-config.md):

- ~10.9MB orphaned `tool_trace.jsonl{,.1}` — logger unwired 2026-07-02; safe to delete.
- 1,921 empty stale `session-env/` dirs (mid-June) — no consumer; confirm harness
  ownership before deleting.
- No TTLs on `jobs/` (36M), `file-history/` (46M), `paste-cache/` — the statusline
  flag-reaper's 14-day opportunistic-TTL pattern is the right template to copy.
- Three beneficial-but-uncommitted dotfiles edits (CLAUDE.md simplifications, README
  cleanup, flag-reaper).
- `~/.claude/cms` symlink is a known single point of failure for Stop/SessionEnd hooks
  (acceptable: source repo is pinned and version-controlled).
- `tools/autoflag.py` verified clean against the documented Stop-hook infinite-loop
  anti-pattern: it checks `stop_hook_active` and never emits a blocking exit code.

## Agent/subagent work

Little to fix. Deliberate model-tiering guidance already matches community consensus
almost verbatim; the industry's "deterministic orchestration" trend (code decides the
order, the model does the thinking) is where `dispatch` and the agent-harness sibling
already sit. Ideas worth considering: Sourcegraph Amp's fixed-role named subagents, if
2–3 ad-hoc subagent roles recur (web-research and repo-mapping shapes are candidates);
Claude Code's per-subagent persistent memory (`memory:` frontmatter) for long-lived
adviser agents. Staleness note: Gemini CLI was retired May 19, 2026 (replaced by
Antigravity CLI) — any references to its conventions are dead.

## Key citations

- "Honest Lying: Understanding Memory Confabulation in Reflexive Agents" —
  arXiv:2605.29463 (May 28, 2026)
- Governance decay under compaction — arXiv:2606.22528 (June 2026)
- Anti-consolidation ablations — arXiv:2605.18854, arXiv:2605.12978 (May 2026)
- Anthropic April 2026 postmortem — anthropic.com/engineering/april-23-postmortem
- "Steering Claude Code" — claude.com/blog (June 18, 2026)
- Dreams (memory consolidation, research preview) —
  platform.claude.com/docs/en/managed-agents/dreams
- Claude Code memory docs — code.claude.com/docs/en/memory
- Copilot Memory 28-day expiry — docs.github.com/en/copilot/concepts/agents/copilot-memory
- Zep bi-temporal memory — arXiv:2501.13956
- OWASP Top 10 for Agentic Applications 2026 — genai.owasp.org (ASI01, ASI06)
- Deontic runtime governance — arXiv:2606.19464; Layered Mutability — arXiv:2604.14717
- Context rot — research.trychroma.com/context-rot; Anthropic effective-context-engineering
  (anthropic.com/engineering/effective-context-engineering-for-ai-agents)
