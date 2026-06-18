# CMS — a context-management system you fork and own

**Agents forget. This is a working system that makes their lessons stick — fork it, run
one script, and the machinery is live in your repo.**

CMS is a **forkable reference implementation** of a context-management system for
AI-assisted projects: a closed loop that mines lessons from your sessions, houses them in
governance that fires at the right moment, and keeps an agent's working context lean and
current. You don't depend on it as an opaque package, and you don't let it scaffold a
project then disconnect — you fork or clone it, run `bootstrap.sh`, and own the result.

## How you use it

1. **Fork or clone, then `./bootstrap.sh`.** It installs Monition (the takeaway store, a
   declared dependency — SQLite backend by default, no extra install), arms the pre-commit
   hook, initializes the store, and points you at a landing zone. Add `--link-global` to
   symlink the shared skills into your `~/.claude` so they're live in every session
   (it backs up anything it would replace).
2. **Work.** The machinery runs as you go: the pre-commit linter blocks mechanical
   violations, matching takeaways inject as context, and the skills (`/dispatch`,
   `/handoff`, `/codify`, `/mine-session`, …) are available.
3. **Learn.** Lessons get mined, housed through an explicit consent gate (never silently),
   and fire back as triggered context. The loop runs again.

```
   work happens
        │
        ▼
   MINE the lesson     (/mine-session, postmortems, concern triage)
        │
        ▼
   HOUSE the lesson    (a takeaway row, a method doc, or a CLAUDE.md rule —
        │               routed by /codify, changed only with consent)
        ▼
   FIRE the lesson     (trigger → payload: matched rows injected,
        │               pre-commit lint, pre-edit reminders)
        ▼
   work happens better — and the loop runs again
```

## Two ways in

- **Fork/clone + `./bootstrap.sh`** — CMS *is* your project's context-management layer;
  you build on top of it and own the machinery as a single source.
- **`./bootstrap.sh <path>`** — apply-to-target: copy the machinery and `starter/`
  templates into an existing repo (accepting the drift a copy implies; for your own
  projects, prefer fork-and-bootstrap so there's one source).

There is no generator to interview you and no per-project "profile" to pick. The machinery
is single-sourced; delete what your fork doesn't need.

## Layout

| Dir | What it is |
|---|---|
| `.claude/skills/` | The shared skills — the live machinery (`dispatch`, `codify`, `handoff`, `mine-session`, `wrap-session`, …). Symlinked into `~/.claude` by `bootstrap --link-global`. |
| `method/` | The knowledge base: one doc per discipline, each stating its trigger. Loaded on demand, never all at once. |
| `tools/` | The runnable machinery: the linter (`cms_lint.py`), the craft-reminder and token hooks, the session extractor. |
| `starter/` | Per-project identity templates (`CLAUDE.md`, `road.md`, `debt.md`, the bucket-generator prompt) that apply-to-target lays into a repo. |
| `monition/` | This repo's own takeaway store (Monition, a declared dependency). |
| `landing/` | The zero-config landing-zone fallback for cross-project context (see below). |
| `docs/DESIGN.md` | Architecture: the four seams, the upstream contract, the roadmap. |
| `bootstrap.sh` | The installer — fork-in-place (`--link-global` optional) or apply-to-target. |

## The landing zone

Context that outlives any single repo — cross-cutting decisions, cross-project handoffs —
resolves through a **landing zone**: `$CMS_LANDING_ZONE` if set, else the in-repo
`landing/` fallback. So a fresh fork runs with zero setup, and a power user can point it at
their own cross-project store (mapping a different internal layout with a thin *personal*
config kept out of this repo). Never a committed symlink; personal store mappings stay out
of the repo. See `landing/README.md`.

## Monition — the takeaway store

Takeaways live in a **Monition** store, a declared dependency `bootstrap` installs (SQLite
by default; Dolt optional behind a seam). Each row carries its own trigger (`trigger_kind`
+ `trigger_spec`) so executors stay dumb, and every disclosure is logged and ratable — the
eval substrate a future firing engine trains against. The boundary: **Monition owns the
machinery** (the store contract, `init`/`sync`/`migrate`); **CMS owns the discipline**
(method, skills, lesson-routing).

## Upstream contract

CMS is the upstream reference. A fork drifts freely; when a downstream lesson survives
having its domain stripped away, it's a **system learning** and can mirror back here —
through the consent gate, never silently. Domain-specific adaptations stay in the fork.

**Status:** forkable reference implementation (2026-06). On a fresh clone, `./bootstrap.sh`
installs the store and arms hooks; to arm the hook alone, `git config core.hooksPath
.githooks`.
