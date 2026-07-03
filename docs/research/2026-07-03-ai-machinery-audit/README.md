# AI-machinery audit — 2026-07-03

An adversarial audit of the full context-management / governance / agent-machinery stack
(CMS, the Monition takeaway store, the global harness configuration, and the landing-zone
vault), compared against industry practice as of May–June 2026 via targeted web research.

## Method

Seven parallel research agents, synthesized by the main session:

- **Four local lenses** — repo/system mappers with read access: the CMS repo itself, the
  Monition system (code repo + hub store, with live SQL queries for real numbers), the
  global `~/.claude` configuration, and the landing-zone vault's machinery health.
- **Three web lenses** — fresh research (window: roughly May 1 – July 2, 2026, plus
  still-canonical older pieces): (1) agent memory + context engineering, (2) Claude Code /
  harness power-user practice, (3) governance, evals, and self-improvement loops.
  Primary sources preferred; secondary sources and single-voice heuristics are labeled
  as such throughout.

Data snapshot: Monition hub numbers and filesystem sizes were measured 2026-07-02
(evening) – 2026-07-03. All counts in these documents are point-in-time; re-query the
store rather than trusting them later.

## Index

| File | Contents |
|------|----------|
| [synthesis.md](synthesis.md) | **The deliverable**: verdict, strengths vs. the frontier, ranked gaps with evidence and recommended moves, hygiene list, key citations |
| [system-cms.md](system-cms.md) | CMS repo inventory: tools, skills, method docs, decisions, hooks wiring, honest gaps |
| [system-monition.md](system-monition.md) | Monition architecture + the critical numbers (rating rates, over-firing, lifecycle) |
| [system-global-config.md](system-global-config.md) | Global harness config: hooks, skills, daemon, accumulation, single points of failure |
| [system-landing-zone.md](system-landing-zone.md) | Landing-zone vault machinery health (sanitized; the vault itself is private) |
| [industry-memory-context.md](industry-memory-context.md) | External research: agent memory architectures, consolidation evidence, context engineering |
| [industry-harness-practice.md](industry-harness-practice.md) | External research: Claude Code / harness configuration state of the art |
| [industry-governance-evals.md](industry-governance-evals.md) | External research: self-improvement loops, governance patterns, rating-loop pitfalls, observability |

## One-line verdict

The capture half of the learning loop (flags, mining, routing, consent, provenance) is
polished past the published frontier; the judgment half (rating coverage, pruning,
behavioral evals of the harness itself) runs at ~10% coverage with a slightly-negative
reading — the next unit of effort belongs almost entirely on the measurement side.

## Scope note (public repo)

This is the public copy: the private vault is referred to generically as "the landing
zone," personal context is omitted, and paths are home-relative. The operator's private
vault holds a companion inbox item with the unsanitized framing.
