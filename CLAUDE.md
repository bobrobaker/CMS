# CMS — working on CMS itself

This repo is a **forkable reference implementation** of a context-management system (see
`README.md`): `bootstrap.sh` installs the machinery live in a fork. Sessions here either
use that machinery or improve it.

## Map

- `method/` — the knowledge base: one doc per discipline, each stating its trigger.
  Loaded on demand, never all at once.
- `.claude/skills/` — the shared skills, single-sourced here and symlinked into the
  author's `~/.claude` (`bootstrap --link-global`); editing one edits both.
- `tools/` — the runnable machinery: the linter, the craft-reminder and token hooks, the
  session extractor.
- `starter/` — per-project identity templates (`CLAUDE.md`, `road.md`, `debt.md`, the
  bucket-generator prompt). Every starter file is a live template: `{{PLACEHOLDERS}}` mark
  the per-project slots.
- `landing/` — the zero-config landing-zone fallback; `$CMS_LANDING_ZONE` overrides it.
- `docs/DESIGN.md` — architecture and roadmap. `tools/cms_lint.py` — this repo's linter.
- `monition/` — this repo's Monition store (SQLite default, Dolt optional; semantics in
  `method/takeaway-store.md`; machinery is the installed Monition module). Hooks inject
  matching rows as you work; mine new ones with `/mine-session`.

## Rules

- **Write for an external reader, from line one.** No source-project provenance in
  `method/`, `starter/`, or skill doc bodies — the linter WARNs on known provenance
  strings. Worked examples are neutral or web-dev flavored. This is the *teaching
  surface* only: the `monition/` store is **not** part of it. The store is
  private-but-versioned working memory mined from real sessions, so rows may carry
  machine-local paths and personal detail (the linter's provenance check scans only
  `method`/`payload`). Keep a row's transferable lesson legible on its own so it still
  benefits when the store is carried to another machine or fork where a local path
  won't resolve — but don't sanitize rows the way teaching docs are sanitized.
- **Read budget:** grep before reading; `grep -n "^##"` before any markdown range read;
  load only the `method/` docs the task touches.
- **Machinery edits follow method.** Before editing a skill or `starter/` template that a
  `method/` doc governs, read that doc (the linter can't check this; you must).
- **Never codify silently.** Behavior-changing edits to `method/` docs, skills, or
  `starter/` templates are proposed and accepted before writing. Downstream lessons mirror
  back only domain-stripped, through the same gate.
- **Design calls leave a record.** Project-internal design decisions land as date-slug
  files in `docs/decisions/` (the call plus its why), so a later session inherits the
  reasoning instead of relitigating it. Cross-cutting calls that outlive this repo go to
  the landing zone's `decisions/`. These files are **provenance**: each carries frontmatter
  `status: decided|superseded` (linted) so retirement is visible at the file, not just in a
  registry. `docs/DESIGN.md` is CMS's live-verdict registry — consult it for *which* call
  currently stands.
- **Mirror-back sweep.** At the start of a session here (or on request), scan downstream
  forks/projects for queued upstream candidates (each appends to its own
  `handoffs/upstream-candidates.md`) and propose them through the consent gate; a landed
  candidate is removed from its downstream queue in the same pass. (Where "downstream"
  lives is environment-specific — e.g. sibling repos under your projects directory.)
- **Rate what fires.** When an injected takeaway helped or was noise, say so:
  `monition rate <firing-id> helpful|noise`. Sparse honest labels beat dense dutiful ones
  — this is the eval data the firing engine will train against.
- **Self-flag flag-worthy moments (tier 1 of the autoflagger).** When a response of yours
  hits a flag-worthy moment — you admit an error, a gotcha recurs, or a "we should make
  this a rule" realization lands — append a `/flag` entry inline (don't wait to be asked,
  don't break flow). You are the judge here: full context, free, more reliable than any
  keyword match. `tools/autoflag.py` (the Stop hook) is only the tier-2 backstop for
  admitted-error phrasing you skip; don't rely on it as the primary path. Routing:
  admitted error / would-have-prevented-this → `GOVERNANCE`; reusable trigger lesson →
  `MONITION`; large costly failure → `POSTMORTEM`; otherwise → `GENERAL`. `/mine-session`
  drains them all at wrap (step 0a).

## Workflow

Pre-commit runs `tools/cms_lint.py` — ERROR blocks, WARN advises. Arm once on a fresh
clone: `git config core.hooksPath .githooks` (or run `./bootstrap.sh`).
