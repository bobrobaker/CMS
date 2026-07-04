---
status: decided
---
# 2026-07-03 · Import AGENTS.md into the starter CLAUDE.md via `@AGENTS.md`

**Decision.** `starter/CLAUDE.md.template` gains a `## Cross-harness agent rules` section
whose body is a single `@AGENTS.md` import line, plus a one-line note explaining it. A
fork that also maintains an `AGENTS.md` (the cross-harness agent-instruction file, now
governed by the Linux Foundation's Agentic AI Foundation) gets it imported into the
Claude Code session; a fork without one is unaffected.

**Why now, and why option (a).** The audit (`docs/research/2026-07-03-ai-machinery-audit/`
§4) flagged AGENTS.md as forward-compatible surface: Claude Code still does not read
`AGENTS.md` natively as of July 2026, so a fork running multiple harnesses needs CLAUDE.md
to pull it in explicitly. Three options were on the table — (a) literal `@AGENTS.md`, (b) a
commented forker-instruction, (c) a `bootstrap.sh` conditional splice. (a) was gated on
one unverified risk: that a *missing* `@import` might error or noisily degrade every fork
that lacks the file.

**Verification that settled it (2026-07-03).** Two headless `claude -p` runs in a scratch
project:
- CLAUDE.md with `@AGENTS.md` and **no** AGENTS.md present → ran clean, empty stderr, no
  error, and the rest of CLAUDE.md still loaded. Missing import is **silently ignored**.
- Then AGENTS.md created carrying a rule reachable *only* through the import → the rule
  took effect. The `@import` mechanism **works** when the file is present.

So (a) is both functional and zero-regression for the majority of forks that have no
AGENTS.md — which retires the reason to prefer (b)'s weak comment or (c)'s extra bootstrap
code. The explanatory line deliberately writes "AGENTS.md" without the `@` so it cannot
trigger a second spurious import; only the bare token on its own line is the live import.

**Provenance / novelty note.** This is the first use of CLAUDE.md `@import` syntax in this
ecosystem — a novel mechanism shipped to every fork, which is why it earns a record rather
than a silent template edit. If a future harness change makes a missing import noisy,
revisit toward option (c) (bootstrap injects the line only when AGENTS.md is present).
