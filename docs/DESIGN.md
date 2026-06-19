# CMS design — seams, contract, roadmap

The architecture behind the system. The README holds the story; this doc holds the
load-bearing decisions.

## What CMS is, precisely

A **forkable reference implementation**, not a generator and not an opaque package. You
fork or clone the repo and run `bootstrap.sh`; the machinery is live in *that* repo, and
the shared parts are **single-sourced** (`.claude/skills/`, `tools/`) rather than copied
per project. One canonical copy, instantly live for the author (via opt-in symlinks),
shipped unchanged to forkers — which is the opposite of the drift a copy-into-N-projects
generator accrues.

The anti-goal is the reading list: a corpus of method docs that a project would have to
*read* to benefit from. A note nobody loads is dead weight, and agents don't browse — so
every method here ships as something that *fires*: a skill, a hook, a linter check, a
prompt, a takeaway row, or a rule in the always-on doc.

## The four seams

1. **Hot ↔ cold context.** Per-file companion notes loaded by path-glob at edit time are
   *hot* context; durable concept docs retrieved on demand are *cold*. A complete system
   needs both temperatures and a promotion/demotion path between them.
2. **One closed learning loop.** Mining lessons (audits, mistake diagnosis) without a
   governed home accretes flat rule files; housing lessons without mining instrumentation
   starves the corpus. The loop is mine → house → fire, closed.
3. **Artifact and claim traceability are the same move.** Data contracts trace *artifacts*
   between pipeline phases; evidence-vs-provenance separation traces *claims* to
   re-consultable backing. Both answer "why should a later consumer trust this?"
4. **The open edge: no value model on firing.** Everything here fires on bare trigger
   match (a glob, a path, a hook, a row's `trigger_spec`). Whether a payload is *worth its
   context cost* — and how hard it should fire — needs a value model. The takeaway store
   (below) is the first step toward it; a full EV-scored firing engine is future work,
   deliberately owned by the Monition module, not this repo.

## The upstream contract

CMS is the upstream reference. A fork **drifts freely** — wires triggers to its own
workload, owns its own feedback logs. At mirror-back time, drift classifies by one rule:
strip the project's domain from the lesson. What survives is a **system learning** and
comes back upstream through the consent gate; what doesn't stays downstream as local
adaptation. Upstream docs grow gotchas and feedback layers only this way — fed by
downstream runs, on saturation, never speculatively.

**Exception — takeaway machinery.** The store schema, executors, and lifecycle CLI are
owned by the **Monition module** and evolve by version bump there, not by copy-and-drift.
CMS declares Monition as a dependency that `bootstrap.sh` installs (SQLite backend by
default; Dolt optional behind a seam). There is no tier-0 floor and no
adopt-from-flat-file graduation: a fork stands up a real store from session one, because
firing provenance (`git_sha`/`session_id`/`situation`) is capture-time-only and can't be
backfilled. The boundary: **Monition owns the machinery** (store contract,
`init`/`sync`/`migrate`); **CMS owns the discipline** (method, skills, the installer,
lesson-routing).

## No profiles

There is no minimal/full profile to choose and no generator to tailor one. The machinery
is single-sourced and a fork takes all of it; **delete what your project doesn't need**
(a doc-shaped project drops the dispatch/bucket apparatus; a solo project drops the
cross-repo confer skill). Adoption is still bottom-up in spirit — grow the feedback and
gotcha layers only when saturation demands — but it's subtractive from one source, not
assembled from tiers.

## Current architecture (what's live)

- **The learning loop.** `mine → house → fire`, closed: `/mine-session` (+ `/flag`,
  `/postmortem`, `/concern-review`) mine; `/codify` routes the lesson to its home (a
  Monition row, a `method/` doc, a `CLAUDE.md` rule, a file-local gotcha); matched rows
  inject as context and the linter/hooks fire mechanically.
- **The takeaway store** — rows + firings live in a single cross-repo **hub**
  (Dolt-backed for us) at `$CMS_LANDING_ZONE/monition`; host repos join it via `monition
  instrument` and keep **no per-repo store** (the former per-repo `monition/` dirs were
  retired in the v6 cutover — see `docs/decisions/2026-06-19-retire-per-repo-stores-and-reference-exhibit.md`).
  A standalone forker with no hub configured still gets its own SQLite `monition/` store.
  Semantics in `method/takeaway-store.md`. Load-bearing invariants: **trigger is data**
  (each row carries `trigger_kind` + `trigger_spec`; executors are dumb) and **every
  disclosure is logged + ratable** (the `firings` table is the eval substrate the firing
  engine trains against). Hooks call the guarded `monition` CLI and fail-open when it's
  absent.
- **Lesson routing** — `method/lesson-routing.md`: ordered destination tests deciding
  whether a mined lesson becomes a store row or a governance-surface edit. Evals are the
  linter for semantic artifacts.
- **Enforcement + observability** — `tools/cms_lint.py` (pre-commit, ERROR blocks / WARN
  advises), `tools/craft_reminder.py` (pre-edit reminder on governed material), and
  `tools/session_tokens.py` (a SessionEnd hook summing API usage into the session log;
  `--print` feeds wrap-up skills).
- **Session archive** — progressive disclosure over session history: capture
  (`/wrap-session`) writes a summary + index entry; retrieval is grep over the ladder plus
  a semantic MCP server over the summary corpus. `tools/extract_session.py` lifts
  role-labelled text from a session JSONL (fail-soft, with a `--canary` mode flagging
  unknown harness record types).
- **The landing zone** — `$CMS_LANDING_ZONE` else the in-repo `landing/` fallback, so a
  fresh fork has a zero-config home for cross-project decisions and handoffs.

## Roadmap (forward)

All deferred work shares one philosophy with the firing engine: gated on accumulated
evidence, never built speculatively.

- **Retrieval routing maturation** — an eval-governed router choosing grep vs. semantic
  search over the governance corpus, gated on retrievals-log volume.
- **Tier-3 evaluation discipline** — evaluating governance lines / prompts / skill text by
  the *rate of a named failure mode* over production traces (the build-out of "evals are
  the linter for semantic artifacts"). CMS owns + ships the discipline (a `method/` doc +
  per-project harness, never a central service); Monition owns + exposes the row-coupled
  substrate (a versioned read-verb + the ΔP(fail) currency); the project owns its traces
  and failure-mode labels. Gated on labeled-trace volume — never day-one.
- **The Monition firing engine** (in the Monition module, not here) — the EV-scored engine
  over the store's `firings` data, replacing hand-tuned `trigger_spec`s and the manual
  rate-and-tighten loop with learned firing decisions. Collection is live; the engine is
  gated on accumulated honest ratings.
- **Store-stays-local hygiene** — the store (hub for us; per-repo for a standalone forker)
  stays local and is never published. Two follow-ups remain on the standalone/forker path:
  `bootstrap.sh` apply-to-target still hardcodes a pre-commit step that git-tracks the store
  dump, and `monition init` still advertises the same; align both with the store-stays-local
  default so a freshly bootstrapped repo ignores its store, with dump-tracking left as an
  explicit opt-in. (Our hub deliberately keeps a tracked `dump.sql` in the private
  landing-zone repo for offsite backup — that's the opt-in, not the default.) Open sub-question: where a *public*-repo project's store gets backed up — since
  it's gitignored, git no longer backs it up, so a private destination is decided per
  project. (Verified safe meanwhile: the published module bundles no store data, so
  installing Monition cannot leak anyone's firings.)

## Porting rules (for anything that enters `method/` or the shared machinery)

- **Generalize, don't copy.** Keep the mechanism + one neutral worked example.
- **Show, don't claim.** Ship the artifact (a runnable hook, a real template) over a
  description of it. This repo dogfoods its own machinery for the same reason.
- **Single source.** One canonical rendering of any rule; derived views are generated,
  never hand-maintained.
- **No provenance in doc bodies.** Origins live in private git history, not in what a
  reader sees. The linter WARNs on known provenance strings.
