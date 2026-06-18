# Summaries — session archives as a cold store

**Trigger:** read when wiring session capture into a project, deciding what a wrapped
session should leave behind, or when retrieval starts surfacing stale summaries.
Operative artifacts: the `/wrap-session` skill (`.claude/skills/wrap-session`), the
trace extractor (`tools/extract_session.py`), and the shared archive (index +
summaries, with grep and semantic retrieval).

## Why a session archive

A finished session holds context — why a thing was built, what was tried and
abandoned — that the code does not. Lost at session end, it gets rediscovered the
expensive way. The archive is a cold store: written once at wrap, read rarely, found
by half-remembered query ("I worked on X once"). It is navigation, not truth — see
§Staleness.

## Progressive disclosure — the four-rung ladder

One session is recorded at four widths, each pointing down to the next:

1. **Index line** — one greppable line per session (date, title, topics). The floor:
   every wrapped session has at least this.
2. **Summary** — an embedding-friendly abstract (goal, what changed, key decisions)
   plus a structured `files:` list of what the session changed (see §Staleness). The
   rung retrieval ranks over.
3. **Extracted transcript** — role-labelled user+assistant text, tool/meta noise
   dropped (`extract_session.py`, fail-soft, `--canary` flags any record type outside
   the known harness schema).
4. **Raw JSONL** — the unabridged session, read by specific line only (one line can be
   tens of KB — see `read-path.md`).

A reader climbs only as far as the question needs. Most stop at rung 2.

## Capture

`/wrap-session` summarizes *from context already in the window* — it never re-reads the
transcript for the prose — and writes the rung-2 summary plus the rung-1 index entry,
reusing the session token log (`session_tokens.py --print`) for the usage marker. Capture
is the archive's write path: cheap, at session end, lossy by design. The one structured
field it does extract mechanically (not from memory) is `files:` — the paths the session
changed, lifted from the transcript's edit-class tool calls by `extract_session.py
--files` — the signal §Staleness depends on.

**Wrapping a session something else tears down.** When an external runner starts a
session and then closes it (an ephemeral worker, a sandboxed job), capture must be the
session's *final live turn* — once the process is gone the window is gone, and the
from-the-window rule above leaves only the transcript, i.e. a rung-3-degraded summary. So
the runner holds teardown until the rung-2 artifact is on disk, and the rung-2 *format*
travels *to* the session (installed payload, else injected into the final-turn prompt)
with only the file coming back — the archive never depends on the runner. N such sessions
in one run collapse to **one** rung-1 line + one rung-2 summary, the sessions as
sub-sections (an independently-findable one is promoted via a takeaway, not a second
entry). The one field that still survives teardown mechanically is `files:` —
`extract_session.py --files` derives it from the saved transcript with no live window.

## Retrieval

Two surfaces over the ladder: grep for exact tokens, a semantic index for why/how
queries (incremental by mtime so reindexing is free). The grep-vs-semantic *routing
rule* lives in `read-path.md` §Retrieval routing — the archive is one corpus that rule
covers. Every retrieval appends to a retrievals log (row format owned by the Monition
module's `retrievals-log.md` contract, cited not duplicated) — the eval substrate a
future router trains against.

## Staleness — don't trust a cached answer blindly

A summary is a snapshot of what was true at wrap; the code keeps moving. So retrieval
annotates the surfaced hit against the substrate: from the captured `files:`, it counts
commits touching those files since the session date and flags the summary
(`⚠ N commit(s) … — summary may be stale`) or confirms it fresh, so the reader sees how
far the ground has moved before climbing further. The boundary is the day *after* the
session (the index carries a date, not a timestamp), so a summary never flags its own
same-day commits as staleness — "stale" means the files were touched on a later day; the
cost is missing a same-day edit made after the wrap. Summaries with no `files:` (older
wraps, backfill stubs) skip the check silently.
The cold-store answer to "never cache a correct answer": don't forbid the cache,
timestamp it against the substrate.

## Wiring & ownership

- Capture ships per-project (`/wrap-session` + `extract_session.py`, whose `--files`
  mode is the staleness-capture source); the index/summary store and retrieval are
  shared infrastructure across projects.
- The archive discipline is canonical here; the retrievals-log row format is owned by
  the Monition module (version-bumped there, cited here).
- The eval-gated grep-vs-semantic retrieval router stays deferred — gated on
  retrievals-log volume, same philosophy as the firing engine. Staleness annotation,
  earlier deferred alongside it, now ships: it is a deterministic git count, not a tuned
  ranking, so it needed no eval data to justify.
