---
status: decided
---

# Semantic-index staleness net lives in housekeep, not capture

**Decision.** The freshness net for the session-archive semantic index is a
`/housekeep` section (§N, auto-fix tier): when any summary in
`~/.claude/logs/sessions/` postdates the ChromaDB index, housekeep runs the
incremental indexer. Capture (`/wrap-session`, `backfill.py`) stays
index-unaware.

**Why housekeep and not a capture-side hook.** Capture happens per-session and
should stay cheap and dependency-free: the indexer needs a heavy venv
(chromadb + sentence-transformers) and pays a model-load cost when work exists,
which is the wrong tax on every session wrap. Housekeep is the existing daily
cadence for exactly this class of drift — an all-skip incremental run costs
seconds, so the net is effectively free when the index is current.

**Why auto-fix rather than propose.** The reindex is idempotent and only
adds/updates index entries — it cannot lose information, which is the
auto-tier's bar. The tier-definition line in the skill was widened to name it
alongside the two mechanical reaps.

**Why the on-use warning wasn't enough.** The only prior staleness signal
printed inside `search_sessions` results — visible on use, not on drift. With
sparse semantic-search usage the index was observed 2 months stale before the
first user-visible symptom. The runbook line claiming "a missed re-index is
visible, not silent" was corrected to name §N as the drift net and the server
note as the on-use backstop.

**Interpreter resolution.** §N resolves the python interpreter and `index.py`
path from the registered `session-archive` MCP server in `~/.claude.json`
rather than any hardcoded venv path — the venv is machine-local and may be
borrowed from another project. No registration → silent skip (the semantic
layer is optional); registered but broken → report-only notice.
