# Read path — budget the reads, author for the retriever

**Trigger:** read when writing a project's `CLAUDE.md` context-hygiene section, when
adding per-file companion notes, or when a project saturates into needing retrieval
routing. The operative artifact is the hygiene block in `starter/CLAUDE.md.template`.

## Read-budget hygiene

A small rule set in the always-on doc that treats input tokens as a budget: every read
must be the cheapest operation that answers the question.

- **Grep for symbols, fields, registries, constants, and call sites before reading any
  file.** Don't open a file to answer a question grep can answer.
- **Structure-scan before any markdown range read:** `grep -n "^##" <file>.md` first,
  then bounded reads of only the needed sections — for *all* docs, not just code.
- **Reads over ~150 lines require a stated reason.** Prefer one complete
  function/class range over multiple partial reads.
- **Separate required from conditional reads up front.** Read only files the change
  touches.
- **Don't re-read what grep or prior output already answered.**
- **Constrain repo-wide greps to source extensions** — unfiltered greps scan binaries
  and logs and can return multi-MB output.
- **Know your file shapes.** One line of a JSONL log can be tens of KB: read a
  specific line, never stream a range; check whether an extraction script exists
  before reading any raw log.

Three meta-rules govern the set itself: hygiene rules are first-class always-on
content (they apply every session — that's the always-on test); each rule names the
wasteful move it bans, not just the right move; and the set stays small because rules
enter only from observed waste in real sessions, never speculation.

**The corpus co-evolves with the budget.** Work docs carry greppable anchors
(`Progress:` markers, conventional headers) and the always-on doc prescribes exact
navigation paths — the comparison question gets a one-grep answer instead of two full
reads.

## Companion notes (hot context)

A companion note is a compact agent-facing note attached to one source file — the
touchpoints, helper patterns, and non-obvious gotchas repeated sessions would
otherwise rediscover. Hot context: loaded at edit time by path-glob trigger, not
retrieved by topic. Notes mirror the source tree (`docs/notes/<relative-path>.md`)
and are hard-capped (~20 lines source-file notes: Gotchas / Touchpoints / Recent
changes; ~15 lines test-file notes: Helpers / Setup pattern). Touchpoints exist so
the agent issues a bounded read of one function instead of a full-file read — the
note pays for itself in saved tokens.

**A note without a triggering rule is invisible** — agents don't browse. Each covered
subtree gets a rule file with a path glob in its frontmatter: *before editing any file
in `src/`, check for a matching note under `docs/notes/`; use its Touchpoints to avoid
full-file reads.* Creating the note is half the job; wiring the trigger is the other
half.

Update discipline: refresh only for reusable, architectural, or mistake-preventing
takeaways — never "because the file changed." On a symbol rename, grep the notes tree
and fix only the hits. Don't create a note silently mid-task; propose it. Every gotcha
should be a trap, not a description.

## Retrieval routing (full profile, on saturation)

A local vector index over the governance/design corpus, exposed as a search tool —
plus the thing most setups omit: an **explicit routing rule in the always-on doc**:

> Use the docs search tool for open-ended *why/how* questions (design rationale, prior
> decisions, history) against `docs/`. Grep for exact tokens — symbols, fields, known
> paths. Skip both when the path is already known.

Semantic search answers questions whose phrasing won't match the text; grep answers
questions with an exact token. The router sits *above* the read-budget rules,
deciding which cheap path to take before any read happens.

Index the governance layer (design docs, workstreams, contracts, session summaries,
the always-on doc, the trigger rules themselves — so the agent can semantically find
its own conventions), never the code (symbols are exact tokens by nature). Chunk
structurally on headers with size caps; every chunk carries file + section metadata so
results cite a re-consultable location. **Make reindexing free** — incremental by
mtime (seconds when nothing changed) — or the reindex habit never forms. Ship a
runbook: reindex commands, debugging recipes, a symptom→fix tuning table.

## Wiring

- Both profiles: the hygiene block ships in `CLAUDE.md` from day one.
- Companion notes: adopt when the *same file* burns a session twice; wire the glob
  rule the same day.
- Retrieval: adopt when the docs corpus outgrows grep (you notice "why" questions
  going unanswered or full-doc reads creeping in). Iteration 2 ships a reference
  skeleton; until then the routing rule above is the spec.
