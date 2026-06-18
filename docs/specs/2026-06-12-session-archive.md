# Session-archive tooling — aligned spec (grill-me output, for sign-off)

Status: awaiting user sign-off. The eval-substrate question was resolved by
confer with the Monition module on 2026-06-12 (decision 8 below).

## Task as understood

When the user has a vague memory of past work ("I remember doing something
about X"), a session can find the correct reference by progressive disclosure
over session history — climbing from cheap index lines to summaries to
transcript excerpts, stopping at the first rung that answers. Retrieval must be
token-efficient and accurate. Today no summary corpus exists: capture must be
built before retrieval has anything to search.

## Goals and non-goals

**Goals**

1. Capture: every session leaves a trace; wrapped sessions leave a rich one.
2. Retrieval: fuzzy-memory queries resolve to the right session and excerpt at
   minimal token cost, via grep and semantic search, with eval-governed routing
   deciding what fires and what enters context.
3. Instrumentation: every lookup is logged (query, rungs climbed, hit/miss,
   tokens spent) — the eval data the future router trains against.

**Non-goals**

- Decision archaeology ("why did we choose X") — a future, separate system
  shaped around architectural-review artifacts, not session logs.
- Codebase exploration — solved elsewhere; explicitly out
  (codebase-memory-mcp indexes code only, not conversations — evaluated and
  set aside).
- A second `/handoff` — handoffs are deliberate, decision-ready saves; this
  covers the sessions nobody hand-curated.
- A pile of unloaded prose — every artifact here is on a retrieval path.

## Scope and boundaries

- **Corpus is global** (`~/.claude/logs/`, all projects, incubated or not);
  machinery is **user-level**, with CMS owning the source and spawning the
  artifacts (the first CMS product that is not per-project payload).
- Decomposition: (a) capture — `/wrap-session` skill + index-line floor;
  (b) backfill — last ~2 weeks of transcripts; (c) retrieval — MCP semantic
  server + grep over the ladder; (d) instrumentation — retrievals log.

## Success criteria (v1)

Name three real things vaguely remembered from past sessions; the tooling
finds the right session and a relevant excerpt for at least two, in under
~10k tokens of retrieval overhead each. (Anecdote, not eval — accepted for v1;
the retrievals log is what turns this into a real eval later.)

## Key constraints

- **Cache-window discipline:** `/wrap-session` is invoked while the session's
  prompt cache is warm (~5-min TTL) and must not re-read anything — it
  summarizes only from context already in the window.
- **Token counts come from the transcript JSONL, not session context:**
  wrap-session calls `session_tokens.py --print` for the session marker and
  provisional counts; the SessionEnd hook writes the final `tokens:` line
  under the marker (the two halves already interlock by design).
- **Fail-open:** archive capture and retrieval must work when monition is
  absent or broken (standing contract from the module-realignment resolution).
- **Hook anchoring:** any hook command anchors to `$CLAUDE_PROJECT_DIR` or an
  absolute user-level path, never the cwd (t5).
- Capture path stays stdlib-and-files; only the semantic layer earns a venv
  (model ~80MB local, ChromaDB), per an established local-embedding pattern.

## Decisions and rationale

| # | Decision | Rationale |
|---|---|---|
| 1 | Capture is human-invoked `/wrap-session`; no LLM at SessionEnd | Hooks can't summarize (no model at hook time); unattended summarization spends API tokens on dead sessions |
| 2 | Archive layout: per-session summary files (`~/.claude/logs/sessions/<date>-<project>-<sessionid>.md`) + one-line index entries in `sessions.md` | Each disclosure rung must be independently loadable; one growing file makes rung 2 cost the whole archive |
| 3 | Ladder: index line → summary file → extracted transcript (user+assistant text) → raw JSONL | Each rung ~10× the tokens of the last; stop at first hit |
| 4 | Both grep and semantic search ship; an eval-governed router decides which fires and what enters context | User decision; dissolves the ship-now-vs-later fork — routing quality is an evals question, same philosophy as monition's firing engine |
| 5 | Semantic search is an MCP server (user-level, one global index over the *summary corpus only*, Chroma + local MiniLM, incremental by mtime) | User preference (discoverability) over CLI default; raw transcripts are noise-dominated and never embedded |
| 6 | Backfill: last ~2 weeks (~170 transcripts, 91MB raw) — extract user+assistant text, cap per session (~50k chars, head+tail), summarize via `claude -p --model haiku` | Day-one quality on exactly the history likely to be fuzzily remembered; extraction cuts raw bytes to ~10–15%; low single-digit dollars |
| 7 | Wrap-session integrates the token analyzer (`--print`) and stamps the session marker | Counts are only in the JSONL; the marker is how the SessionEnd hook finds the entry to finalize |
| 8 | Retrievals log: separate flat file day one, no monition dependency, fail-open. CMS drafts the schema; **monition owns it at birth** as a sibling contract doc in monition's `docs/contracts/` (CMS cites, never duplicates). Draft must carry: additive-column rule, version stamp, outcome semantics aligned with `firings` (`helpful\|noise`, NULL = unrated). Router graduates to monition when it grows a non-per-project-store surface (recorded in monition's roadmap) | Confer resolution 2026-06-12: monition's `firings` is takeaway-bound (FK + dedup against `takeaways`), no user-level store exists or is planned; matches the tier-0 interchange precedent (realignment decision 13) and t9 owner-at-birth |

## Defaults adopted

**Firm (user-confirmed):** decisions 1–7 above; success criteria; non-goals;
CMS spawns the machinery.

**Tentative (unobjected defaults — revisit only if they become suspicious):**

- Index-line floor: every session gets a mechanical index line (date · project
  · first user message · token totals) even when never wrapped — nothing is
  invisible, just sometimes shallow.
- Sessions older than the backfill window get index lines only; LLM-summarize
  lazily on first retrieval touch.
- Per-session backfill input cap ~50k chars, head+tail split.
## Open questions (deferred)

1. Summary entry schema (sections, staleness annotations) — implementation
   detail, settled at build time against a summary-metadata pattern.
