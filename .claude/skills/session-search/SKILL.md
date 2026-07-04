---
name: session-search
description: Search the global session archive to answer "have I done this before?" — the retrieval side of the archive that /wrap-session captures into. Routes a query across the grep ladder (recall.py, exact keywords) and semantic search (search_sessions, fuzzy/conceptual recall). Use when the user says "dejavu?", "have we done this before?", "didn't I work on X already?", "did I solve this in a past session?", "search my sessions for X", or you're about to build/decide something that feels previously-trodden. NOT for archiving the current session (that's /wrap-session) and NOT for a decision-ready resume of in-flight work (that's /handoff).
---

# session-search

Answer a fuzzy-memory query against the **global session archive** — the corpus
`/wrap-session` and `backfill.py` write into (`~/.claude/logs/sessions*`). "Dejavu?"
is the canonical evocation: *this feels like something I've hit before — find it.*

The archive is global machinery reached through the dotfile anchor `~/.claude/cms`
(the `bootstrap --link-global` symlink). Both retrieval paths write one row to
`~/.claude/logs/retrievals.jsonl` — the signal a future router trains on.

## Two retrieval paths — route by query shape

There is **no learned router yet**; use the v1 rule of thumb, cheapest-first:

| Query shape | Use |
|---|---|
| Exact keyword / known term / a *what* lookup | `recall.py` (grep ladder, cheapest) |
| Fuzzy / conceptual / "I remember *something about*…" | `search_sessions` (semantic) |

A bare "dejavu?" with no named target is usually **fuzzy** → lead with semantic; if
the user names a concrete term ("the night-queue drain bug"), lead with grep.

**Grep ladder** — climbs index → summary and stops at the first rung with hits
(transcript/raw are opt-in, `--max-rung transcript`):

```bash
python3 ~/.claude/cms/archive/recall.py <query words>          # e.g. … night queue drain
python3 ~/.claude/cms/archive/recall.py --top 8 <query words>  # widen the result set
```

**Semantic** — the `mcp__session-archive__search_sessions` MCP tool
(`search_sessions(query, n_results)`), embeddings over the summary corpus. Use for
conceptual recall where the exact words won't match. If the tool is absent (a
headless/cron run where the server isn't registered), fall back to
`recall.py --max-rung summary` and say so.

## Protocol

1. **Classify the query** (fuzzy vs exact) and pick the lead path. When unsure or the
   lead returns nothing, try the other — the two miss on different query shapes.
2. **Run it, present the hits** — day, project, title, and the summary path/anchor so
   the user (or you) can open the full session. Don't dump transcripts; the summary is
   the recall unit.
3. **If nothing lands**, say so plainly and offer to climb a rung
   (`--max-rung transcript`) or rephrase — don't manufacture a false match.
4. **Rate a hit post-hoc** to seed the router signal, when the user reacts:
   `python3 ~/.claude/cms/archive/recall.py --rate <retrieval-id> helpful|noise`.

**Fail open.** A missing corpus, unregistered MCP server, or absent CLI is a notice,
not an error — report what's unavailable and use whatever path remains.
