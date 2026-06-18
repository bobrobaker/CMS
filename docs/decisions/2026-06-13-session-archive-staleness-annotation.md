# 2026-06-13 · Session-archive staleness annotation: build now, capture-side

**Decision.** Built the staleness annotation the session-archive spec had filed under
"Open questions (deferred)". Retrieval now annotates the surfaced summary with how far
its files have moved since the session:

- **Capture (source A).** `extract_session.py` gains a `--files` mode that lifts the
  distinct paths the session *edited* — from `Edit`/`Write`/`MultiEdit`/`NotebookEdit`
  tool calls only — deterministically from the transcript. `/wrap-session` records them
  as a `files:` YAML list in the summary frontmatter.
- **Annotation.** `recall.py` parses `files:`, groups them by git repo, counts commits
  touching them since the session date, and prints `⚠ N commit(s) … — summary may be
  stale` (or `✓ fresh`) under the top hit.

**Why build now (vs. the spec's deferral).** The spec lumped staleness with the
grep-vs-semantic router in one "deferred, gated on retrievals-log volume" bucket. That
rationale fits the router — a *tuned ranking* that needs usage data to settle — but was
over-applied here: a commit count is a *deterministic fact*, so it needs no eval data to
justify. Carrying it as deferred work also has a real standing cost (tracking it,
re-explaining "why not yet"); paying down a cheap deterministic item beats holding it.

**Why source A (capture-time) over B (retrieval-time git date-window).** A records what
the session *actually* edited; B would infer from a date window and conflate multiple
same-day sessions in one repo. A is also deterministic and needs no project→path map.

**Design calls within the build.**
- `files:` lives in the **summary frontmatter**, not the index line. Verified safe for
  the semantic index: `index.py` embeds `title + abstract + body`, and `body` excludes
  frontmatter; `parse_frontmatter` skips YAML list items. The lean index line stays lean.
- Repo is resolved from each file's **git toplevel** (grouped per repo), not a
  `~/projects/<name>` convention — so multi-repo sessions work and nothing assumes a path.
- **Edit-class tools only.** First cut counted any `file_path`, which swept in `Read`
  targets (context, not work products); caught in testing, filtered to writers.

**Owner + channel (t9).** `summaries.md` is the canonical discipline. `--files` ships to
generated projects via `payload/tools/extract_session.py`; capture via
`payload/skills/wrap-session/`; the annotation lives in the shared `archive/recall.py`.

**Boundary — revised same day via dogfood.** First implemented as "count commits since
the session day 00:00" (over-warn, accepted as the safe direction). Wrapping this very
session showed the flaw: a session commits its own work the same day it wraps, so that
boundary makes every summary flag *itself* stale on its own commits — permanently —
gutting the signal. (The first cut also had a bare-date bug: git approxidate fills a
bare date's missing time from the current wall clock, so `--since <day>` drifted with
the clock; the boundary must be an explicit datetime.) Revised to anchor at the **day
after** the session: "stale" = files touched on a *later* day, so the session's own
commits never count. Cost: a same-day edit made after the wrap is missed — acceptable
for a solo, commit-then-wrap workflow.

**Limitations (accepted).** Only the top hit is annotated (extending to all surfaced
matches is trivial). Summaries with no `files:` (older wraps, backfill stubs) skip the
check.

**Still deferred.** The eval-gated grep-vs-semantic retrieval router — correctly, since
it is the tuned-ranking half the eval-gating rationale was actually about. And precise
**wrap-timestamp granularity** (capture an exact wrap time; `--since` that) — the proper
fix for the same-day-after-wrap miss, deferred as low-value for the common workflow.
