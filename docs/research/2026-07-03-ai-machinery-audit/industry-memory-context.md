# Industry lens — agent memory & context engineering (state of practice, July 2026)

Web research, window May 1 – July 2, 2026 plus still-canonical older pieces. Primary
sources preferred; confidence labels inline. Verification note: the Anthropic "Dreams"
feature was cross-checked against the official docs page after one research pass found
only third-party coverage — it is real and official
(platform.claude.com/docs/en/managed-agents/dreams, beta header `dreaming-2026-04-21`).

## 1. Memory architectures

**Episodic/semantic/procedural framing.** The LLM-agent adaptation of Tulving's
taxonomy traces to CoALA (arXiv:2309.02427, Sep 2023) and is being refined, not
replaced: a Jan–Feb 2026 survey keeps it as one axis of three (arXiv:2602.06052); a May
2026 paper proposes Storage→Reflection→Experience instead (arXiv:2605.06716, May 7).
*Fashion flag:* "the ecosystem converged on CoALA" appears only in SEO blogs; no major
coding-agent vendor doc uses the taxonomy officially.

**Consolidation/decay/dedup — the evidence is thin and cuts against heavy
consolidation:**

- A 480-run coding-agent ablation found **no LLM condenser improved output quality**;
  summarizers added 24–94% token cost while cheap tool-output masking won
  (arXiv:2605.18854, May 2026).
- A second paper measured consolidation *harm*: **54% of previously-solved problems
  failed post-consolidation** (arXiv:2605.12978, May 13, 2026).
- **Mem0 reversed course in production**, deprecating ADD/UPDATE/DELETE consolidation
  for ADD-only accumulation + temporal ranking (docs.mem0.ai, 2026). Its own July 2
  "State of AI Agent Memory" report admits it weights agent self-confirmations equal to
  user-stated facts and calls staleness unsolved
  (mem0.ai/blog/state-of-ai-agent-memory-2026).
- **Anthropic Dreams** (research preview): async reorganization of a memory store from
  past transcripts — dedup, stale-entry replacement — with the input store never
  modified, output reviewable/discardable. The non-destructive, human-reviewable design
  is itself a signal of how cautiously the lab treats auto-consolidation.
- **Zep's bi-temporal pattern** (arXiv:2501.13956, Jan 2025): contradicted facts marked
  invalid, never deleted — *supersede, don't delete* is the other convergent pattern.

**Injection vs. retrieval-on-demand.** No study directly isolates hook-based injection
vs. agent-initiated retrieval for coding agents — a **genuine empirical gap**. Nearest
evidence: Anthropic recommends a hybrid (some pre-loaded, just-in-time exploration at
agent discretion — anthropic.com/engineering/effective-context-engineering-for-ai-agents,
Sep 29, 2025); a 3×3 factorial study found retrieval method matters far more than write
strategy (14–23 pts vs 3–8 — arXiv:2603.02473v2, Apr 2026); one weak 9-run benchmark
found injected memory cut turns/cost 22–40% on complex tasks without improving code
quality (Medium, Mar 2026 — low confidence). The converging *production* pattern is
**injection-with-validation**: GitHub Copilot Memory re-validates stored facts against
the current branch and **expires them after 28 days unused**
(docs.github.com/en/copilot/concepts/agents/copilot-memory, May–June 2026); Letta keeps
core memory always in-context, archival tool-retrieved. Broad trend: flat, inspectable,
file-based memory with expiry and human gating, over vector/graph DBs
(arXiv:2602.23368).

## 2. Context engineering from the labs

- **Context rot is established and mechanistically explained.** Chroma's canonical
  study: 18 models degrade well before nominal context limits
  (research.trychroma.com/context-rot, Jul 2025). Anthropic's explanation: n² attention
  over training distributions favoring short sequences; degradation is a gradient, not
  a cliff (Sep 2025). A June 2026 study evaluated seven mitigations across
  compaction/trimming/isolation: compaction+trimming best on cost/quality; sub-agent
  isolation highly model-dependent (arXiv:2606.29718v1).
- **Vendor-reported, not replicated:** Opus 4.6 Compaction API numbers (76% vs 18.5%
  MRCR at 1M) via tech press (InfoQ, Mar 2026).
- **Budgets & progressive disclosure.** Anthropic: context is a finite budget;
  lightweight references in context, full content just-in-time — no hard numbers. The
  circulating concrete numbers (~256K effective ceiling, ~20-tool surface,
  compact-oldest-20-turns) come largely from one practitioner
  (philschmid.de/context-engineering-part-2, Dec 2025) — credible but a single voice.
  Same source warns that *dynamically* fetching instructions by semantic similarity
  breaks KV-cache and confuses models — static core instructions + lazy data loading
  preferred. Cursor shipped a Context Usage Breakdown observability feature
  (cursor.com/changelog/05-06-26, May 6, 2026).
- **Instruction-file design — real cross-vendor convergence** (all official docs): keep
  the always-on file short (Anthropic's test: "would removing this cause mistakes?";
  sometimes-relevant knowledge → on-demand Skills); Cursor: rules <500 lines, split
  into glob-conditionally-loaded `.mdc` files; Copilot: ≤2 pages + path-scoped
  `.instructions.md`; Codex: 32KiB cap, nested closest-wins. Anthropic gotcha:
  CLAUDE.md `@import` does **not** save tokens — imports load at launch. The
  "150–200 instructions" limit figure is third-party, not Anthropic.
- **AGENTS.md** is now governed by the Linux Foundation's Agentic AI Foundation
  (OpenAI and Anthropic Platinum founders; MCP co-donated — LF press release, Dec 9,
  2025). Adopters: Codex, Cursor, Devin, Copilot, Zed, Aider ("60,000+ projects" is
  unaudited). **Correction to widespread blog claims: Claude Code still does not
  natively read AGENTS.md** as of July 2026 (open issues #11455/#6235, no changelog
  entry through v2.1.198; workaround: symlink/import).

## 3. May–June 2026 releases relevant to lesson-learning systems

- **Anthropic Dreams** (verified primary source) — the clearest new thing in-window.
- **Claude Code changelog:** CLAUDE.md-too-long warning scaled to model context window
  (v2.1.162, Jun 3); MEMORY.md compaction reminder near size limit (v2.1.181, Jun 17);
  team memory store fixes (code.claude.com/docs/en/changelog).
- **"Honest Lying: Understanding Memory Confabulation in Reflexive Agents"**
  (arXiv:2605.29463, May 28, 2026) — the most important paper in-window for
  lesson-learning systems. In frozen ALFWorld environments, **0 of 121 Reflexion-style
  self-generated reflections identified the correct failure cause** — agents stored
  confident, wrong interpretations and repeated them. Replacing open-ended
  self-critique with *programmatic failure-signal extraction* raised correctness
  0%→86%.
- **Letta:** product consolidation (Letta Code app, Apr 6, 2026); no new
  MemGPT-lineage paper in-window. No A-MEM update found.
- Devin/Windsurf consolidation keeps AGENTS.md as the maintained instruction path
  (devin.ai/blog, Jun 2, 2026); Codex v0.142.0 loads AGENTS.md from foreign
  environments (Jun 22, 2026).

## 4. Converged failure modes

- **Memory poisoning formalized:** OWASP ASI06 (Agentic Top 10, 2026), distinguished
  from prompt injection by persistence; MINJA/InjecMEM show >95% injection success
  against production memory agents with no privileged access
  (openreview.net/forum?id=QVX6hcJ2um). Mostly adversarial framing — adjacent to, not
  identical with, benign staleness.
- **Governance decay** (arXiv:2606.22528, June 2026): compaction silently drops
  standing policy/instruction entries scored low-salience — constraint violations rose
  0%→30–59% across 1,323 episodes; soft policies decayed 8.3× faster than hard safety
  norms. Measured, non-adversarial, directly relevant to any system whose standing
  rules ride in compactable context.
- **Over-injection/noise:** retrieval accuracy peaks around 3–5 injected chunks and
  degrades beyond (vectorize.io, 2026 — directional, not rigorous). **No published
  methodology exists for detecting when an injection system has gone net-negative** —
  open gap.
- **Unvalidated self-lesson loops:** "Honest Lying" is now the citable evidence;
  self-generated evaluation is "inherently biased, inconsistent, unstable"
  (arXiv:2603.25681, 2026). No documented production incident of compounding
  lesson-drift — argued from first principles plus that lab result.
- **Staleness:** Copilot's 28-day-unused expiry is the only shipped, concrete staleness
  policy found. **No source proposes a validated "hasn't fired in N sessions → prune"
  cadence** — that idea has no external convergence yet. CLAUDE.md line-count limits in
  circulation are unvalidated blog heuristics.

## Read on the audited system

1. The audited architecture (short always-on CLAUDE.md + on-demand method docs +
   separate handoff-vs-memory machinery) matches official cross-vendor guidance almost
   exactly; `/handoff` occupies a space vendors have documented demand for (issue
   #11455) but not shipped.
2. "Honest Lying" argues *mined* lessons need grounding in programmatic/outcome
   signals, not model self-diagnosis — the helpful/noise rating labels are exactly the
   validation layer the literature says self-lesson systems lack (see synthesis Gaps 1
   and 4).
3. The injection-vs-retrieval bet the takeaway store makes has **no direct empirical
   answer anywhere** — its own rating data may be the best available instrument.
4. Copilot's re-validate-plus-expire and Zep's supersede-don't-delete are the two
   shipped staleness patterns to compare against (synthesis Gap 3).

**Meta-lesson from the research process itself:** subagents disagreed on the
verification status of the same fact (Dreams); "I couldn't find a primary source" is
absence of search luck, not absence of source. SEO/aggregator sites systematically
overstate vendor support (Claude Code + AGENTS.md the clearest case) and re-date old
features as new. One subagent relayed a fabricated paper statistic that only re-fetching
the abstract caught — paper numbers relayed by agents need independent verification.
