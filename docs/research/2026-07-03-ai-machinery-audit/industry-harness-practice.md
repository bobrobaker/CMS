# Industry lens — Claude Code / harness configuration state of the art (May–June 2026)

Web research; official sources (anthropic.com/engineering, code.claude.com/docs,
claude.com/blog) distinguished from community/secondary throughout.

## 1. Anthropic's own recent guidance

**"Steering Claude Code: skills, hooks, rules, subagents and more"** — claude.com/blog,
June 18, 2026. Names seven instruction mechanisms (CLAUDE.md, path-scoped rules,
skills, subagents, hooks, output styles, `--append-system-prompt`), each with different
context cost and enforcement strength. Explicit guidance: CLAUDE.md ≤200 lines; move
procedures into skills; move hard guardrails into hooks/managed settings — **CLAUDE.md
is context, not enforcement**; prefer path-scoped rules.

**First-party memory** (code.claude.com/docs/en/memory) — the most load-bearing find
for this audit:

- **Auto memory** (default-on since v2.1.59, Feb 2026): per-repo self-written notes
  (`MEMORY.md` + topic files); first 200 lines/25KB load every session; topic files on
  demand.
- **Subagent persistent memory** (`memory: user|project|local` frontmatter): a durable
  per-subagent memory directory, read-before/write-after. Pull-based, not
  trigger-matched.
- **Dreams / "Auto Dream"**: background consolidation — verified official as a research
  preview (platform.claude.com/docs/en/managed-agents/dreams).

Key structural distinction: first-party memory is repo-scoped, unprompted, and loads a
fixed head-of-file blob — it is **not** trigger-matched against the current prompt,
cross-repo, or rateable. A trigger store does something structurally different;
collapsing one into the other would be a downgrade, not a simplification (see
synthesis, strength 1).

**Checkpointing** (code.claude.com/docs/en/checkpointing): every prompt auto-checkpoints
file-edit state; `/rewind` restores; 30-day persistence; does not track bash-command
writes. A safety net, not a memory system — but don't duplicate "undo" tooling.

**Plugins**: official marketplace (`anthropics/claude-plugins-official`) bundles
skills + hooks + MCP + subagents; the sanctioned distribution unit for generic skills.

**The April 2026 postmortem** (anthropic.com/engineering/april-23-postmortem and
companion post): ~six weeks (Mar 4 – Apr 20) of degraded Claude Code output from three
stacked product-layer changes — (1) default reasoning effort dropped high→medium
(Mar 4, reverted Apr 7 as "the wrong tradeoff"); (2) a thinking-clearing optimization
that fired every turn instead of once per idle session (fixed Apr 10); (3) a
system-prompt verbosity cap causing a measured ~3% quality drop (Apr 16, reverted
Apr 20). **The single most relevant why-you-should-eval-your-setup data point: teams
running their own workflow evals caught the regression in ~72 hours vs six weeks for
everyone on vibes.**

Other surface changes: Sonnet 5 default with 1M context; `claude mcp login/logout`;
background-session reliability across restarts.

## 2. Community state of the art

- **CLAUDE.md size discipline** is near-consensus and matches official guidance:
  <200 lines, front-load priority rules, delete what the model already does, procedures
  → skills, hard rules → hooks. (Secondary sources converging with the official post.)
- **Hook anti-patterns** (cross-corroborated; reference repo
  `disler/claude-code-hooks-mastery`):
  - *Stop-hook infinite loop*: a blocking Stop hook that always fires → work/stop/block
    cycle. Fix: check `stop_hook_active` in hook input, or bounded-retry termination.
    (Verified clean in this system's autoflag.py.)
  - *Exit-code mixups*: only exit 2 blocks; other nonzero is logged-and-ignored — a
    guard returning 1 silently no-ops while looking armed.
  - *Stray stdout*: diagnostics on stdout corrupt structured-output hooks; use stderr.
- **Subagent orchestration**: community sweet spot 3–5 concurrent subagents
  (merge overhead beyond); documented ceiling 10 per orchestrator. Model tiering:
  reasoning-heavy orchestration on top-tier, mechanical extraction on cheap tier.
- **"Dynamic Workflows" / deterministic orchestration** (June 2026, moderately
  corroborated — flag as less certain): move the orchestration loop itself (ordering,
  branching, model routing, stopping condition) into code, not the lead agent's
  reasoning — "the model does the thinking, the code decides the order" — to scale past
  what one context can hold.
- **AGENTS.md convergence**: Claude Code docs recommend `@AGENTS.md` import or symlink
  rather than duplication; `/init` ingests existing `.cursorrules` /
  `.windsurfrules` / AGENTS.md. Candidate convention for `starter/CLAUDE.md.template`:
  import AGENTS.md if present.

## 3. Competing harnesses (June 2026)

- **Gemini CLI retired at Google I/O (May 19, 2026)**, replaced by Antigravity CLI; old
  tool stopped serving June 18. References to its conventions are stale.
- **Codex CLI**: GPT-5.5 default, first-party Ollama support; nothing
  governance/memory-shaped worth stealing this cycle.
- **Sourcegraph Amp**: fixed-role named subagents — Oracle (code analysis), Librarian
  (external research), Painter (image gen) — plus a "deep mode" for extended runs. The
  role-fixing pattern is worth considering for 2–3 constantly recurring subagent roles.
- **Cursor 3.7 (June 2026)**: UI-level memory deletion + prompts letting automation
  "delete outdated memories when it runs" — pruning as first-class UI, parallel to
  Dreams. Signal: memory *pruning*, not just accumulation, is table-stakes across
  harnesses.
- No credible evidence of a competing harness pulling ahead of the converged primitive
  set (rules file + skills + hooks + subagent memory + checkpoint/rewind) this cycle.

## 4. Evals/testing for agent configs — documented, still niche, most actionable

The three-layer testing pyramid (secondary synthesis, consistent with official
eval-tool docs at platform.claude.com/docs/en/test-and-evaluate/eval-tool):

1. **Hook tests** — shell-script tests per commit: dangerous ops blocked, safe ops pass.
2. **Skill evals** — parallel subagent runs, blind A/B against a rubric written
   *before* the run; checks output quality *and* trigger/activation accuracy.
3. **Workflow evals** — full-system runs (CLAUDE.md + skills + hooks + subagents +
   model version) against 5–10 canonical tasks, headless
   (`claude --headless --output-format stream-json`), LLM-judge scored, diffed against
   a recorded regression baseline (e.g. weighted-average drop >0.3 triggers
   investigation). **Scheduled (weekly CI), not only on change** — vendor-side
   regressions arrive without a local diff.

Practitioner norm for eval sets: small (30–200 examples), hand-labeled once, versioned
in-repo, re-run on every prompt/hook/skill change — regression tests for prompt
machinery. Documented and cross-corroborated, but clearly minority behavior; most
published "best practices" content is about *writing* configs, not *testing* them.

Read on the audited system: CMS has the structural layer (linter, hook unit tests,
mirror-parity) and none of the behavioral layer — the natural next tier is the workflow
eval, which is a materially different check (behavioral, not structural). See synthesis
Gap 5.
